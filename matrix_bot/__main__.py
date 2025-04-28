import asyncio
import logging
import sys
from aiohttp import web
import signal
import functools

import simplematrixbotlib as botlib
from . import config as config_module
from . import commands
from . import webhooks

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

# --- Global Runner for Cleanup ---
webhook_runner = None
site = None

async def main():
    global webhook_runner, site

    # --- Check Config ---
    if not config_module.creds or not config_module.config_instance:
        logger.critical("Configuration or credentials failed to load. Exiting.")
        sys.exit(1)
    config = config_module.config_instance

    # --- Create Bot ---
    bot = botlib.Bot(config_module.creds)

    # --- Register Commands ---
    prefix = config.command_prefix
    commands.register_all(bot, config, prefix)

    # --- Setup Webhook Server ---
    webhook_app = web.Application()
    webhook_app['bot'] = bot
    webhook_app['config'] = config
    webhooks.setup_webhook_routes(webhook_app)

    webhook_runner = web.AppRunner(webhook_app)
    await webhook_runner.setup()
    site = web.TCPSite(webhook_runner, config.webhook_host, config.webhook_port)

    # --- Start Webhook Server & Run Bot ---
    try:
        # Start the webhook server first
        await site.start()
        logger.info(f"Webhook server started on http://{config.webhook_host}:{config.webhook_port}")

        logger.info("Starting Matrix bot main loop...")
        # *** FIX: Call bot.main() instead of bot.run() ***
        await bot.main()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping bot...")
    except Exception as e:
        logger.exception(f"An error occurred during bot execution: {e}")
    finally:
        logger.info("Cleaning up webhook server...")
        if webhook_runner:
            await webhook_runner.cleanup()
            logger.info("Webhook server stopped.")
        else:
            logger.warning("Webhook runner was not initialized.")

        logger.info("Attempting to close Matrix client session...")
        if bot and bot.api and bot.api.async_client:
             try:
                 await bot.api.async_client.close()
                 logger.info("Matrix client session closed.")
             except Exception as close_exc:
                 logger.error(f"Error closing Matrix client session: {close_exc}")
        else:
             logger.warning("Matrix client session was not available for closing.")


if __name__ == "__main__":
    logger.info("Starting bot application...")
    try:
        asyncio.run(main())
    except Exception as global_error:
        logger.exception(f"Unhandled exception in global execution scope: {global_error}")
    finally:
        logger.info("Application finished.")
