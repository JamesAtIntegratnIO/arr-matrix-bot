import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom

# Import your config module structure
from .. import config as config_module
# Import the status check utilities AND the message sending utility
from ..utils import matrix_utils, status_utils
from typing import Dict

logger = logging.getLogger(__name__)

COMMAND_NAME = "status"

# --- Help Registration ---
def register_help(help_registry: Dict[str, Dict[str, str]], prefix: str):
    """Registers the help text for the status command."""
    command_key = "status" # Or use COMMAND_NAME if defined

    # Define description and usage separately
    description = "Checks the connection status of the bot and integrated services."
    usage = (
        f"{prefix}{command_key}\n"
        f"  Checks the status of all connected services (Matrix, Sonarr, Radarr, etc.).\n\n"
    )

    # Assign a DICTIONARY to the registry
    help_registry[command_key] = {
        "description": description,
        "usage": usage
    }
    logger.debug(f"Registered help for command: {command_key}")

async def _status_command_handler(room: MatrixRoom, message: RoomMessageText, bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
    """Handles the !status command."""
    # --- Check 1: Ignore messages from the bot itself ---
    if message.sender == config.matrix_user:
        return

    # --- Check 2: Ignore messages not from the target room ---
    if config.target_room_id and room.room_id != config.target_room_id:
        # Log for debugging if needed, but don't clutter normal operation
        # logger.debug(f"Ignoring command from {message.sender} in room {room.room_id} (not target room)")
        return
    # --- End Room Check ---

    full_command = prefix + COMMAND_NAME

    # --- Check 3: Check if the message is the command ---
    if not message.body.strip().lower() == full_command:
        return

    # If we passed all checks, proceed with handling the command
    logger.info(f"Received status command from {message.sender} in room {room.room_id}")

    # Perform the checks using the utility function
    try:
        status_results = await status_utils.check_all_services(bot, config)
    except Exception as e:
        logger.error(f"Unexpected error during status check triggered by command: {e}", exc_info=True)
        # Use matrix_utils to send error message
        await matrix_utils.send_formatted_message(
            bot, room.room_id, # Send error back to the command room
            "Error: An unexpected error occurred while checking service status.",
            "<p>Error: An unexpected error occurred while checking service status.</p>"
        )
        return

    # Format the report using the utility function
    plain_report, html_report = status_utils.format_status_report(status_results)

    # Send the report back to the room where the command was issued using matrix_utils
    await matrix_utils.send_formatted_message(bot, room.room_id, plain_report, html_report)

# --- register function remains the same ---
def register(bot: botlib.Bot, config_obj: config_module.MyConfig, prefix: str):
    """Registers the status command handler with the bot."""
    async def handler_wrapper(room, message):
        try:
            await _status_command_handler(room, message, bot, config_obj, prefix)
        except Exception as handler_exc:
            logger.error(f"Unhandled exception in _status_command_handler: {handler_exc}", exc_info=True)
            try:
                await bot.api.async_client.room_send(
                    room_id=room.room_id,
                    message_type="m.room.message",
                    content={ "msgtype": "m.notice", "body": "Sorry, an internal error occurred processing the status command."}
                )
            except Exception as report_exc:
                logger.error(f"Failed to report internal status handler error to room {room.room_id}: {report_exc}")

    bot.listener.on_message_event(handler_wrapper)
    logger.info(f"Status command '{prefix}status' registered (target room: {config_obj.target_room_id or 'Any'}).")
# --- END OF register FUNCTION ---