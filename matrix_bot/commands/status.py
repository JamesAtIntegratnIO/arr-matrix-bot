import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom

# Import your config module structure
from .. import config as config_module
# Import the status check utilities AND the message sending utility
from ..utils import matrix_utils, status_utils

logger = logging.getLogger(__name__)

async def _status_command_handler(room: MatrixRoom, message: RoomMessageText, bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
    """Handles the !status command."""
    # Ignore messages from the bot itself
    if message.sender == config.matrix_user:
        return

    command_name = "status"
    full_command = prefix + command_name

    # Check if the message is exactly the command
    if not message.body.strip().lower() == full_command:
        return

    logger.info(f"Received status command from {message.sender} in room {room.room_id}")

    # Perform the checks using the utility function
    try:
        status_results = await status_utils.check_all_services(bot, config)
    except Exception as e:
        logger.error(f"Unexpected error during status check triggered by command: {e}", exc_info=True)
        # Use matrix_utils to send error message
        await matrix_utils.send_formatted_message(
            bot, room.room_id,
            "Error: An unexpected error occurred while checking service status.",
            "<p>Error: An unexpected error occurred while checking service status.</p>"
        )
        return

    # Format the report using the utility function
    plain_report, html_report = status_utils.format_status_report(status_results)

    # Send the report back to the room where the command was issued using matrix_utils
    await matrix_utils.send_formatted_message(bot, room.room_id, plain_report, html_report)

# --- THIS FUNCTION IS REQUIRED by commands/__init__.py ---
def register(bot: botlib.Bot, config_obj: config_module.MyConfig, prefix: str):
    """Registers the status command handler with the bot."""
    # Create a closure to capture bot, config_obj, and prefix for the handler
    async def handler_wrapper(room, message):
        try:
            # Call the actual command logic handler
            await _status_command_handler(room, message, bot, config_obj, prefix)
        except Exception as handler_exc:
            # Log any unhandled exceptions from the command handler itself
            logger.error(f"Unhandled exception in _status_command_handler: {handler_exc}", exc_info=True)
            # Try to report a generic error back to the room
            try:
                # Use underlying client for simple text message on error
                await bot.api.async_client.room_send(
                    room_id=room.room_id,
                    message_type="m.room.message",
                    content={ "msgtype": "m.notice", "body": "Sorry, an internal error occurred processing the status command."}
                )
            except Exception as report_exc:
                # Log if even reporting the error fails
                logger.error(f"Failed to report internal status handler error to room {room.room_id}: {report_exc}")

    # Register the wrapper function to listen for message events
    bot.listener.on_message_event(handler_wrapper)
    logger.info(f"Status command '{prefix}status' registered.")
# --- END OF register FUNCTION ---