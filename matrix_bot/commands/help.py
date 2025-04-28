import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom
from .. import config as config_module
from ..utils import matrix_utils
import html

logger = logging.getLogger(__name__)

# HELP_COMMANDS dictionary remains the same
HELP_COMMANDS = {
    "help": { "description": "Shows this help message.", "usage": "help [command]" },
    "sonarr": {
        "description": "Searches Sonarr or gets info about a series.",
        "usage": ("sonarr [search] [--unadded] <search_term>\n  `search`: Optional keyword.\n  `--unadded`: Show only results not yet in Sonarr.\n  `<search_term>`: The name of the series to search for.\n\nsonarr info <tvdb_id>\n  `info`: Get detailed info and poster for a specific series.\n  `<tvdb_id>`: The TVDb ID of the series.")
    },
    "radarr": {
        "description": "Searches Radarr or gets info about a movie.",
        "usage": ("radarr [search] [--unadded] <search_term>\n  `search`: Optional keyword.\n  `--unadded`: Show only results not yet in Radarr.\n  `<search_term>`: The name of the movie to search for.\n\nradarr info <tmdb_id>\n  `info`: Get detailed info and poster for a specific movie.\n  `<tmdb_id>`: The TMDb ID of the movie.")
    },
}


async def _help_command_handler(room: MatrixRoom, message: RoomMessageText, bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
    """Handles the help command, sending formatted output."""
    # --- Ignore messages from the bot itself ---
    if message.sender == config.matrix_user:
        return
    # -------------------------------------------

    command_name = "help"
    full_command = prefix + command_name

    if not message.body.startswith(full_command): return

    # ... rest of the help handler logic remains the same ...
    args_part = message.body[len(full_command):].strip(); args = args_part.split()
    plain_body = ""; html_body = ""
    if not args:
        plain_body = f"Available commands (prefix with '{prefix}'):\n\n"; html_body = f"Available commands (prefix with <code>{html.escape(prefix)}</code>):<br/><br/>"
        for cmd, info in HELP_COMMANDS.items():
            cmd_esc = html.escape(cmd); desc_esc = html.escape(info.get('description', 'No description available.'))
            plain_body += f"{cmd}: {info.get('description', 'No description available.')}\n"; html_body += f"<strong>{cmd_esc}</strong>: {desc_esc}<br/>"
        plain_body += f"\nType `{prefix}help <command>` for more details."; html_body += f"<br/>Type <code>{html.escape(prefix)}help &lt;command&gt;</code> for more details."
    else:
        target_cmd = args[0].lower()
        if target_cmd.startswith(prefix): target_cmd = target_cmd[len(prefix):]
        if target_cmd in HELP_COMMANDS:
            info = HELP_COMMANDS[target_cmd]; cmd_with_prefix = f"{prefix}{target_cmd}"; cmd_esc_prefix = html.escape(cmd_with_prefix); desc_esc = html.escape(info.get('description', 'N/A'))
            plain_body = f"{cmd_with_prefix}\n\n"; html_body = f"<strong>{cmd_esc_prefix}</strong><br/><br/>"
            plain_body += f"Description: {info.get('description', 'N/A')}\n\n"; html_body += f"Description: {desc_esc}<br/><br/>"
            usage = info.get('usage')
            if usage:
                formatted_usage_plain = usage.replace(f"{target_cmd} ", f"{prefix}{target_cmd} "); formatted_usage_html = html.escape(formatted_usage_plain).replace("\n", "<br/>")
                plain_body += f"Usage:\n{formatted_usage_plain}"; html_body += f"Usage:<br/><pre><code>{formatted_usage_html}</code></pre>"
            else: plain_body += "Usage: N/A"; html_body += "Usage: N/A"
        else:
            cmd_esc = html.escape(target_cmd); prefix_esc = html.escape(prefix)
            plain_body = f"Unknown command: '{target_cmd}'. Type `{prefix}help` to see available commands."; html_body = f"Unknown command: <code>{cmd_esc}</code>. Type <code>{prefix_esc}help</code> to see available commands."

    await matrix_utils.send_formatted_message(bot, room.room_id, plain_body, html_body)


# register function remains the same
def register(bot: botlib.Bot, config_obj: config_module.MyConfig, prefix: str):
    async def handler_wrapper(room, message): await _help_command_handler(room, message, bot, config_obj, prefix)
    bot.listener.on_message_event(handler_wrapper)
    logger.info("Help command registered.")
