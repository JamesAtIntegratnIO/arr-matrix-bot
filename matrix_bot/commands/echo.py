import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom
from .. import config as config_module # Use the imported config module
from typing import Dict

logger = logging.getLogger(__name__)

COMMAND_NAME = "echo"

def register_help(help_registry: Dict[str, Dict[str, str]], prefix: str):
    """Registers the help text for the echo command."""
    command_key = "echo" # Or use COMMAND_NAME if defined

    # Define description and usage separately
    description = "Echoes back the message you send."
    usage = f"{prefix}{command_key} <message>"

    # Assign a DICTIONARY to the registry
    help_registry[command_key] = {
        "description": description,
        "usage": usage
    }
    logger.debug(f"Registered help for command: {command_key}")

async def _echo_command_handler(room: MatrixRoom, message: RoomMessageText, bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
    """Handles the actual echo command logic after filtering."""
    full_command = prefix + COMMAND_NAME

    # --- Add command filtering logic here ---
    if not message.body.startswith(full_command):
        return # Ignore messages not starting with the command
    # ---------------------------------------

    # Extract arguments
    args_text = message.body[len(full_command):].strip()
    logger.info(f"Received echo command from {message.sender} in room {room.room_id}")

    if not args_text:
        await bot.api.send_text_message(room.room_id, f"Usage: {prefix}echo <message>")
        return

    await bot.api.send_text_message(room.room_id, args_text)

def register(bot: botlib.Bot, config_obj: config_module.MyConfig, prefix: str):
    """Registers the echo command listener."""
    async def handler_wrapper(room, message):
        # Call the actual handler, passing all necessary arguments
        await _echo_command_handler(room, message, bot, config_obj, prefix)

    # Register the wrapper with the message event listener
    bot.listener.on_message_event(handler_wrapper)
    logger.info("Echo command registered.")
