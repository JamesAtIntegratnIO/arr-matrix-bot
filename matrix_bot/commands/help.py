import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom
from .. import config as config_module
from ..utils import matrix_utils
import html
from typing import Dict

logger = logging.getLogger(__name__)
COMMAND_NAME = "help" # Command name without prefix

# --- Help Registration for THIS command ---
def register_help(help_registry: Dict[str, Dict[str, str]], prefix: str):
    """Registers the help text for the 'help' command itself."""
    command_key = COMMAND_NAME
    help_registry[command_key] = {
        "description": "Shows available commands or detailed help for a specific command.",
        "usage": f"{prefix}{COMMAND_NAME}\n  Shows a list of all available commands.\n\n"
                 f"{prefix}{COMMAND_NAME} <command>\n  Shows detailed usage for the specified <command>."
    }
    logger.debug(f"Registered help for command: {command_key}")

# --- Main Command Handler ---
async def _help_command_handler(
    room: MatrixRoom,
    message: RoomMessageText,
    bot: botlib.Bot,
    config: config_module.MyConfig,
    prefix: str,
    # --- Accepts the completed registry ---
    help_registry: Dict[str, Dict[str, str]]
):
    """Handles the help command using the dynamically built help_registry."""
    # --- Ignore messages from the bot itself ---
    if message.sender == config.matrix_user:
        return
    # --- Ignore messages not from the target room (if configured) ---
    if config.target_room_id and room.room_id != config.target_room_id:
        return
    # -------------------------------------------

    full_command_prefix = prefix + COMMAND_NAME

    # Only react if the message starts with the help command prefix
    if not message.body.strip().lower().startswith(full_command_prefix):
        return

    logger.info(f"Received help command from {message.sender} in room {room.room_id}")

    # Extract arguments after "!help"
    args_part = message.body[len(full_command_prefix):].strip()
    args = args_part.split()

    plain_body = ""
    html_body = ""

    # Case 1: General help (!help)
    if not args:
        plain_body = f"Available commands (prefix with '{prefix}'):\n\n"
        html_body = f"Available commands (prefix with <code>{html.escape(prefix)}</code>):<br/><br/><ul>"
        # --- Use the passed-in help_registry ---
        for cmd, info in sorted(help_registry.items()): # Sort for consistent order
            cmd_esc = html.escape(cmd)
            desc_esc = html.escape(info.get('description', 'No description available.'))
            plain_body += f"{cmd}: {info.get('description', 'No description available.')}\n"
            html_body += f"<li><strong>{cmd_esc}</strong>: {desc_esc}</li>"
        plain_body += f"\nType `{prefix}help <command>` for more details."
        html_body += f"</ul><br/>Type <code>{html.escape(prefix)}help &lt;command&gt;</code> for more details."

    # Case 2: Specific command help (!help <command>)
    else:
        target_cmd = args[0].lower()
        # Allow using the command with or without prefix in the help argument
        if target_cmd.startswith(prefix):
            target_cmd = target_cmd[len(prefix):]

        # --- Use the passed-in help_registry ---
        if target_cmd in help_registry:
            info = help_registry[target_cmd]
            cmd_with_prefix = f"{prefix}{target_cmd}"
            cmd_esc_prefix = html.escape(cmd_with_prefix)
            desc_esc = html.escape(info.get('description', 'N/A'))

            plain_body = f"{cmd_with_prefix}\n\n"
            html_body = f"<strong>{cmd_esc_prefix}</strong><br/><br/>"
            plain_body += f"Description: {info.get('description', 'N/A')}\n\n"
            html_body += f"Description: {desc_esc}<br/><br/>"

            usage = info.get('usage')
            if usage:
                # Usage might already contain the prefix, or might assume it.
                # Let's display it as provided in the registry.
                usage_esc = html.escape(usage)
                # Ensure newlines in usage are rendered correctly in HTML <pre>
                usage_html_formatted = usage_esc.replace('\n', '<br/>')
                plain_body += f"Usage:\n{usage}"
                # Use <pre><code> for better formatting of multi-line usage
                html_body += f"Usage:<br/><pre><code>{usage_html_formatted}</code></pre>"
            else:
                plain_body += "Usage: N/A"
                html_body += "Usage: N/A"
        else:
            cmd_esc = html.escape(target_cmd)
            prefix_esc = html.escape(prefix)
            plain_body = f"Unknown command: '{target_cmd}'. Type `{prefix}help` to see available commands."
            html_body = f"Unknown command: <code>{cmd_esc}</code>. Type <code>{prefix_esc}help</code> to see available commands."

    # Send the assembled message
    await matrix_utils.send_formatted_message(bot, room.room_id, plain_body, html_body)


# --- Main Registration function for the command LISTENER ---
def register(
    bot: botlib.Bot,
    config_obj: config_module.MyConfig,
    prefix: str,
    # --- Accepts the completed registry from commands/__init__.py ---
    help_registry: Dict[str, Dict[str, str]]
):
    """Registers the help command listener."""
    # Create a closure to capture bot, config_obj, prefix, AND the help_registry
    async def handler_wrapper(room, message):
        try:
            # Pass the captured help_registry to the handler
            await _help_command_handler(room, message, bot, config_obj, prefix, help_registry)
        except Exception as handler_exc:
            logger.error(f"Unhandled exception in _help_command_handler: {handler_exc}", exc_info=True)
            # Try to report a generic error back to the room
            try:
                await bot.api.async_client.room_send(
                    room_id=room.room_id,
                    message_type="m.room.message",
                    content={"msgtype": "m.notice", "body": f"Sorry, an internal error occurred processing the {prefix}help command."}
                )
            except Exception as report_exc:
                logger.error(f"Failed to report internal help handler error to room {room.room_id}: {report_exc}")

    # Register the wrapper function to listen for message events
    bot.listener.on_message_event(handler_wrapper)
    logger.info(f"Help command '{prefix}{COMMAND_NAME}' listener registered.")
