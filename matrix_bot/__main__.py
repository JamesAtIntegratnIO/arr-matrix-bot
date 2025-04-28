import asyncio
import logging
import sys
from aiohttp import web
# Removed signal and functools - not needed for this approach

import simplematrixbotlib as botlib
# Assuming these imports work based on your project structure
from . import config as config_module
from . import commands
from . import webhooks # Keep this for the actual Radarr webhook logic

# --- Logging Setup ---
log_level = logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("aioopenssl").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("nio").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Simple Health Check Handlers ---
async def handle_healthz(request: web.Request):
    """Liveness probe: Checks if the web server process is running."""
    logger.debug("Received /healthz request")
    return web.Response(status=200, text="OK")

async def handle_readyz(request: web.Request):
    """Readiness probe: Checks if the web server process has started."""
    # Basic check: If the server is running, consider it ready for K8s purposes.
    # More complex checks involving bot state could be added later if needed.
    logger.debug("Received /readyz request")
    return web.Response(status=200, text="Ready")

# --- Main Application ---
async def main():
    # Keep track of the web server task
    web_server_task = None
    webhook_runner = None
    site = None

    # --- Check Config ---
    if not config_module.creds or not config_module.config_instance:
        logger.critical("Configuration or credentials failed to load. Exiting.")
        sys.exit(1)
    config = config_module.config_instance
    logger.info("Configuration loaded.")

    # --- Create Bot ---
    bot = botlib.Bot(config_module.creds)
    logger.info("Matrix Bot instance created.")

    # --- Register Bot Commands ---
    prefix = config.command_prefix
    commands.register_all(bot, config, prefix)
    logger.info(f"Registered bot commands with prefix '{prefix}'.")

    # --- Setup Webhook Server ---
    webhook_app = web.Application()
    # Pass bot/config for the actual Radarr webhook handler
    webhook_app['bot'] = bot
    webhook_app['config'] = config

    # --- Add Routes ---
    # Add the actual Radarr webhook route (from webhooks.py)
    webhooks.setup_webhook_routes(webhook_app) # Ensure this ONLY adds the /webhook/radarr route now
    # Add the health check routes
    webhook_app.router.add_get('/healthz', handle_healthz)
    logger.info("Registered liveness probe route: /healthz (GET)")
    webhook_app.router.add_get('/readyz', handle_readyz)
    logger.info("Registered readiness probe route: /readyz (GET)")

    # --- Prepare Runner and Site ---
    webhook_runner = web.AppRunner(webhook_app)
    await webhook_runner.setup()
    site = web.TCPSite(webhook_runner, config.webhook_host, config.webhook_port)
    logger.info("Webhook AppRunner setup complete.")

    # --- Start Webhook Server in Background & Run Bot ---
    try:
        # Start the webhook server as a background task
        logger.info(f"Attempting to start web server on http://{config.webhook_host}:{config.webhook_port}...")
        await site.start() # Start the site
        logger.info("Web server started successfully.")
        # --- NOTE: site.start() doesn't return a task directly.
        # The server runs in the background managed by the runner.
        # We just need to ensure cleanup happens.

        logger.info("Starting Matrix bot main loop (blocking)...")
        # This will block until the bot stops or is interrupted
        await bot.main() # Use the original blocking call

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping bot and web server...")
    except Exception as e:
        logger.exception(f"An error occurred during main execution: {e}")
    finally:
        logger.info("Initiating shutdown sequence...")

        # 1. Stop the bot (implicitly handled by bot.main() exiting or erroring)
        #    Add explicit close just in case.
        logger.info("Attempting to close Matrix client session...")
        if bot and bot.api and bot.api.async_client:
             try:
                 await bot.api.async_client.close()
                 logger.info("Matrix client session closed.")
             except Exception as close_exc:
                 logger.error(f"Error closing Matrix client session: {close_exc}")
        else:
             logger.warning("Matrix client session was not available for closing.")

        # 2. Stop the web server
        logger.info("Cleaning up webhook server runner...")
        if webhook_runner:
            try:
                await webhook_runner.cleanup()
                logger.info("Webhook server runner stopped.")
            except Exception as runner_exc:
                logger.error(f"Error cleaning up webhook runner: {runner_exc}")
        else:
            logger.warning("Webhook runner was not initialized, skipping cleanup.")

if __name__ == "__main__":
    logger.info("Starting bot application...")
    try:
        asyncio.run(main())
    except Exception as global_error:
        logger.exception(f"Unhandled exception in global execution scope: {global_error}")
        sys.exit(1) # Exit with error on unhandled exception
    finally:
        logger.info("Application finished.")
