import asyncio
import logging
import sys
from aiohttp import web

import simplematrixbotlib as botlib
from . import config as config_module
from . import commands
from . import webhooks

# Import Status and Matrix Utils
from .utils import status_utils
from .utils import matrix_utils

# Logging Setup
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


# Health Check Handlers
async def handle_healthz(request: web.Request):
    """Liveness probe: Checks if the web server process is running."""
    logger.debug("Received /healthz request")
    return web.Response(status=200, text="OK")

async def handle_readyz(request: web.Request):
    """Readiness probe: Checks if the web server process has started."""
    logger.debug("Received /readyz request")
    return web.Response(status=200, text="Ready")


# Main Application
async def main():
    webhook_runner = None
    site = None

    # Check Config
    if not config_module.creds or not config_module.config_instance:
        logger.critical("Configuration or credentials failed to load. Exiting.")
        sys.exit(1)
    config = config_module.config_instance
    logger.info("Configuration loaded.")

    # Create Bot
    bot = botlib.Bot(config_module.creds)
    logger.info("Matrix Bot instance created.")

    # Register Bot Commands
    prefix = config.command_prefix
    commands.register_all(bot, config, prefix)
    logger.info(f"Registered bot commands with prefix '{prefix}'.")

    # --- STARTUP STATUS CHECK ROUTINE (Using target_room_id) ---
    async def run_startup_checks(_unused_arg):
        logger.info("Startup routine initiated...")
        # Use config.target_room_id instead of matrix_startup_room_id
        if not config.target_room_id:
            logger.warning("No target_room_id configured. Skipping startup status report.")
            return

        # Perform checks
        try:
            status_results = await status_utils.check_all_services(bot, config)
            plain_report, html_report = status_utils.format_status_report(status_results)

            # Use config.target_room_id for sending the message
            target_room = config.target_room_id
            logger.info(f"Sending startup status report to target_room_id: {target_room}")
            await matrix_utils.send_formatted_message(
                bot, target_room, plain_report, html_report
            )
            logger.info("Startup status report sent successfully.")
        except Exception as e:
            logger.error(f"Failed to perform or send startup status check: {e}", exc_info=True)
            # Attempt to send an error message if possible
            try:
                 # Use config.target_room_id for error reporting too
                 target_room = config.target_room_id
                 if target_room: # Only try if target_room_id is set
                     await matrix_utils.send_formatted_message(
                        bot, target_room,
                        "Error: Failed to perform startup status checks.",
                        "<p>Error: Failed to perform startup status checks. Check logs.</p>"
                     )
                 else:
                     logger.error("Cannot report startup check error: target_room_id is not set.")
            except Exception as report_err:
                 logger.error(f"Failed even to report the startup check error: {report_err}")

    # Register the startup check
    bot.listener.on_startup(run_startup_checks)
    logger.info("Registered startup status check routine.")
    # --- END STARTUP STATUS CHECK ROUTINE ---


    # Setup Webhook Server
    webhook_app = web.Application()
    webhook_app['bot'] = bot
    webhook_app['config'] = config # Pass loaded config to webhook handlers if needed

    # Add Routes
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


    # Prepare Runner and Site
    webhook_runner = web.AppRunner(webhook_app)
    await webhook_runner.setup()
    site = web.TCPSite(webhook_runner, config.webhook_host, config.webhook_port)
    logger.info("Webhook AppRunner setup complete.")


    # Start Webhook Server & Run Bot
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
        # Cleanup
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
    logger.info("Starting bot application...")
    try:
        asyncio.run(main())
    except Exception as global_error:
        logger.exception(f"Unhandled exception in global execution scope: {global_error}")
        sys.exit(1)
    finally:
        logger.info("Application finished.")