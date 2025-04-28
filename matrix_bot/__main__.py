import asyncio
import logging
import sys
from aiohttp import web

import simplematrixbotlib as botlib
from . import config as config_module
from . import commands
from . import webhooks # Imports handle_radarr_webhook, handle_sonarr_webhook

# --- *** Import Status and Matrix Utils *** ---
from .utils import status_utils
from .utils import matrix_utils
# --- *** END IMPORT *** ---

# --- Logging Setup ---
# ... (logging setup remains the same) ...
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


# --- Simple Health Check Handlers (remain the same) ---
async def handle_healthz(request: web.Request):
    """Liveness probe: Checks if the web server process is running."""
    logger.debug("Received /healthz request")
    return web.Response(status=200, text="OK")

async def handle_readyz(request: web.Request):
    """Readiness probe: Checks if the web server process has started."""
    logger.debug("Received /readyz request")
    return web.Response(status=200, text="Ready")


# --- Main Application ---
async def main():
    webhook_runner = None
    site = None

    # --- Check Config ---
    if not config_module.creds or not config_module.config_instance:
        logger.critical("Configuration or credentials failed to load. Exiting.")
        sys.exit(1)
    config = config_module.config_instance # Get loaded config instance
    logger.info("Configuration loaded.")

    # --- Create Bot ---
    bot = botlib.Bot(config_module.creds) # Use loaded creds
    logger.info("Matrix Bot instance created.")

    # --- Register Bot Commands ---
    prefix = config.command_prefix
    commands.register_all(bot, config, prefix) # Pass loaded config
    logger.info(f"Registered bot commands with prefix '{prefix}'.")

    # --- *** ADD STARTUP STATUS CHECK ROUTINE *** ---
    async def run_startup_checks():
        logger.info("Startup routine initiated...")
        # Use the config object loaded in main()
        if not config.matrix_startup_room_id:
            logger.warning("No matrix_startup_room_id configured. Skipping startup status report.")
            return

        # Perform checks
        try:
            # Pass the bot instance and the loaded config
            status_results = await status_utils.check_all_services(bot, config)
            plain_report, html_report = status_utils.format_status_report(status_results)

            logger.info(f"Sending startup status report to {config.matrix_startup_room_id}")
            await matrix_utils.send_formatted_message(
                bot, config.matrix_startup_room_id, plain_report, html_report
            )
            logger.info("Startup status report sent successfully.")
        except Exception as e:
            logger.error(f"Failed to perform or send startup status check: {e}", exc_info=True)
            # Attempt to send an error message if possible
            try:
                 await matrix_utils.send_formatted_message(
                    bot, config.matrix_startup_room_id,
                    "Error: Failed to perform startup status checks.",
                    "<p>Error: Failed to perform startup status checks. Check logs.</p>"
                 )
            except Exception as report_err:
                 logger.error(f"Failed even to report the startup check error: {report_err}")

    # Register the startup check to run after login
    bot.listener.on_startup(run_startup_checks)
    logger.info("Registered startup status check routine.")
    # --- *** END STARTUP STATUS CHECK ROUTINE *** ---


    # --- Setup Webhook Server ---
    webhook_app = web.Application()
    webhook_app['bot'] = bot
    webhook_app['config'] = config # Pass loaded config to webhook handlers if needed

    # --- Add Routes ---
    # Radarr Route (use handler from webhooks.py)
    webhook_app.router.add_post('/webhook/radarr', webhooks.handle_radarr_webhook)
    logger.info("Registered Radarr webhook route: /webhook/radarr (POST)")

    # Sonarr Route (use handler from webhooks.py)
    webhook_app.router.add_post('/webhook/sonarr', webhooks.handle_sonarr_webhook)
    logger.info("Registered Sonarr webhook route: /webhook/sonarr (POST)")

    # Health check routes
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
        logger.info(f"Attempting to start web server on http://{config.webhook_host}:{config.webhook_port}...")
        await site.start()
        logger.info("Web server started successfully.")

        logger.info("Starting Matrix bot main loop (blocking)...")
        await bot.main() # This blocks until the bot stops

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping bot and web server...")
    except Exception as e:
        logger.exception(f"An error occurred during main execution: {e}")
    finally:
        # --- Cleanup ---
        logger.info("Initiating shutdown sequence...")

        # Close Matrix client session first
        logger.info("Attempting to close Matrix client session...")
        if bot and bot.api and bot.api.async_client:
             try:
                 await bot.api.async_client.close()
                 logger.info("Matrix client session closed.")
             except Exception as close_exc:
                 logger.error(f"Error closing Matrix client session: {close_exc}")
        else:
             logger.warning("Matrix client session was not available for closing.")

        # Cleanup webhook server runner
        logger.info("Cleaning up webhook server runner...")
        if webhook_runner:
            try:
                await webhook_runner.cleanup()
                logger.info("Webhook server runner stopped.")
            except Exception as runner_exc:
                logger.error(f"Error cleaning up webhook runner: {runner_exc}")
        else:
            logger.warning("Webhook runner was not initialized, skipping cleanup.")

        # Note: site.stop() is implicitly handled by runner.cleanup() for TCPSite

if __name__ == "__main__":
    # ... (__main__ execution block remains the same) ...
    logger.info("Starting bot application...")
    try:
        asyncio.run(main())
    except Exception as global_error:
        logger.exception(f"Unhandled exception in global execution scope: {global_error}")
        sys.exit(1)
    finally:
        logger.info("Application finished.")