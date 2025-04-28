import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom, RoomSendResponse, RoomSendError # Keep RoomSendError if used elsewhere, otherwise remove
from .. import config as config_module
from ..services import sonarr as sonarr_service
from ..utils import matrix_utils # Import the generic senders
import html
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

UNADDED_ONLY_FLAG = "--unadded"

# _send_formatted_message removed

# --- Handler: Process 'info' Subcommand (Uses Generic Card Sender) ---
# ... (remains the same, already calls matrix_utils.send_media_info_card)
async def _handle_sonarr_info(tvdb_id: int, room: MatrixRoom, bot: botlib.Bot, config: config_module.MyConfig):
    logger.info(f"Handling sonarr info request for TVDb ID: {tvdb_id}")
    lookup_query = f"tvdb:{tvdb_id}"
    lookup_results = sonarr_service.search_sonarr_lookup(lookup_query, config.sonarr_url, config.sonarr_api_key)
    if lookup_results is None: await bot.api.send_text_message(room.room_id, f"Error: Could not communicate with Sonarr API while looking up TVDb ID {tvdb_id}."); return
    if not lookup_results: await bot.api.send_text_message(room.room_id, f"Sonarr could not find any series matching TVDb ID {tvdb_id}."); return
    series_lookup_data = lookup_results[0]
    series_id = series_lookup_data.get('id', 0); is_added = series_id > 0
    data_for_card = None; tvdb_id_from_lookup = series_lookup_data.get('tvdbId')
    if is_added:
        logger.info(f"TVDb ID {tvdb_id_from_lookup or tvdb_id} found in Sonarr with ID {series_id}. Fetching details.")
        details = sonarr_service.get_sonarr_series_details(series_id, config.sonarr_url, config.sonarr_api_key)
        if not details: await bot.api.send_text_message(room.room_id, f"Found series with TVDb ID {tvdb_id_from_lookup or tvdb_id} in Sonarr, but failed to fetch its details."); return
        if 'tvdbId' not in details and tvdb_id_from_lookup: details['tvdbId'] = tvdb_id_from_lookup
        elif 'tvdbId' not in details: details['tvdbId'] = tvdb_id
        data_for_card = details
    else:
        logger.info(f"TVDb ID {tvdb_id_from_lookup or tvdb_id} found via lookup, but not added to Sonarr.")
        if 'tvdbId' not in series_lookup_data and tvdb_id_from_lookup: series_lookup_data['tvdbId'] = tvdb_id_from_lookup
        elif 'tvdbId' not in series_lookup_data: series_lookup_data['tvdbId'] = tvdb_id
        data_for_card = series_lookup_data
    if data_for_card:
        await matrix_utils.send_media_info_card(bot=bot, room_id=room.room_id, media_data=data_for_card, is_added=is_added, config=config, media_type='series')
    else:
        logger.error("Failed to prepare data for Sonarr info card."); await bot.api.send_text_message(room.room_id, "An internal error occurred.")


# --- Main Command Handler (Uses Generic Formatted Sender for Search) ---
async def _sonarr_command_handler(room: MatrixRoom, message: RoomMessageText, bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
    # --- Ignore messages from the bot itself ---
    if message.sender == config.matrix_user:
        return
    # -------------------------------------------
    command_name = "sonarr"; full_command = prefix + command_name
    usage_string = f"""Usage:\n  `{prefix}{command_name} [search] [{UNADDED_ONLY_FLAG}] <search_term>`\n  `{prefix}{command_name} info <tvdb_id>`"""
    if not message.body.startswith(full_command): return
    args_part = message.body[len(full_command):].strip(); args = args_part.split()
    if not args: await bot.api.send_text_message(room.room_id, usage_string); return

    if args[0].lower() == "info":
        # ... (info handling remains the same, calls _handle_sonarr_info) ...
        if len(args) != 2: await bot.api.send_text_message(room.room_id, f"Usage: `{prefix}{command_name} info <tvdb_id>`"); return
        try:
            tvdb_id_arg = int(args[1]);
            if tvdb_id_arg <= 0: raise ValueError("TVDb ID must be positive.")
            if not config.sonarr_url or not config.sonarr_api_key: await bot.api.send_text_message(room.room_id, "Error: Sonarr is not configured."); return
            await _handle_sonarr_info(tvdb_id_arg, room, bot, config)
            return
        except ValueError: await bot.api.send_text_message(room.room_id, f"Invalid TVDb ID. Usage: `{prefix}{command_name} info <tvdb_id>`"); return

    # --- Search Logic ---
    show_unadded_only = False; search_term_words = []; args_copy = list(args)
    if UNADDED_ONLY_FLAG in args_copy: show_unadded_only = True; args_copy.remove(UNADDED_ONLY_FLAG)
    if args_copy and args_copy[0].lower() == "search": search_term_words = args_copy[1:]
    else: search_term_words = args_copy
    if not search_term_words: await bot.api.send_text_message(room.room_id, usage_string); return
    search_term = " ".join(search_term_words)
    if not config.sonarr_url or not config.sonarr_api_key: await bot.api.send_text_message(room.room_id, "Error: Sonarr is not configured."); return
    logger.info(f"Received sonarr search command from {message.sender} (Unadded: {show_unadded_only}) for: '{search_term}'")
    lookup_results = sonarr_service.search_sonarr_lookup(search_term, config.sonarr_url, config.sonarr_api_key)

    if lookup_results is None: await bot.api.send_text_message(room.room_id, "Error: Sonarr API communication failed."); return
    elif not lookup_results: await bot.api.send_text_message(room.room_id, f"No series found matching '{search_term}'."); return
    else:
        # --- Build Search Results List ---
        added_plain = []; added_html = []; unadded_plain = []; unadded_html = []
        max_unadded = float('inf') if show_unadded_only else 5
        for series_lookup_data in lookup_results:
            # ... (logic to populate added/unadded lists remains the same) ...
            title = series_lookup_data.get('title', 'N/A'); year = series_lookup_data.get('year', 'N/A'); tvdb_id = series_lookup_data.get('tvdbId', 'N/A')
            series_id = series_lookup_data.get('id', 0); is_added = series_id > 0; season_count_lookup = series_lookup_data.get('seasonCount', 0)
            line_base = f"{html.escape(title)} ({year}) [TVDb: {tvdb_id}]"
            if is_added:
                if not show_unadded_only:
                    details = sonarr_service.get_sonarr_series_details(series_id, config.sonarr_url, config.sonarr_api_key)
                    season_count = season_count_lookup; status = 'N/A'; monitored = False
                    if details:
                        seasons_list = details.get('seasons', []); stats = details.get('statistics', {})
                        season_count = len(seasons_list) if seasons_list else stats.get('seasonCount', season_count_lookup)
                        status = details.get('status', 'N/A'); monitored = details.get('monitored', False)
                    else: logger.warning(f"Could not fetch details for added series ID {series_id} (search list).")
                    status_ind = ""; status_ind_h = ""
                    if monitored: status_ind = " (Monitored)"; status_ind_h = " (Monitored)"
                    elif status != 'ended': status_ind = f" ({status.capitalize()})"; status_ind_h = f" ({html.escape(status.capitalize())})"
                    added_plain.append(f"- {line_base} - {season_count} seasons{status_ind}"); added_html.append(f"<li>{line_base} - {season_count} seasons{status_ind_h}</li>")
            else:
                if len(unadded_plain) < max_unadded: unadded_plain.append(f"- {line_base} - {season_count_lookup} seasons"); unadded_html.append(f"<li>{line_base} - {season_count_lookup} seasons</li>")

        # --- Format Body ---
        plain_body = ""; html_body = ""; search_term_esc = html.escape(search_term)
        # ... (logic to build plain_body and html_body remains the same) ...
        if show_unadded_only:
            plain_body = f"Sonarr results for '{search_term}' (Not Added Only):\n\n"; html_body = f"Sonarr results for '<i>{search_term_esc}</i>' (Not Added Only):<br><br>"
            if unadded_plain:
                 plain_body += "\n".join(unadded_plain); html_body += f"<ul>{''.join(unadded_html)}</ul>"
                 total_unadded = sum(1 for s in lookup_results if s.get('id', 0) == 0)
                 if len(unadded_plain) < total_unadded: more = f"\n... and {total_unadded - len(unadded_plain)} more."; plain_body += more; html_body += html.escape(more).replace('\n', '<br>')
            else: plain_body += "No unadded series found."; html_body += "No unadded series found."
        else:
            plain_body = f"Sonarr results for '{search_term}':\n\n"; html_body = f"Sonarr results for '<i>{search_term_esc}</i>':<br><br>"
            plain_body += "-- Added --\n"; html_body += "<b>-- Added --</b><br>"
            if added_plain: plain_body += "\n".join(added_plain); html_body += f"<ul>{''.join(added_html)}</ul>"
            else: plain_body += "None found."; html_body += "None found.<br>"
            plain_body += "\n\n-- Not Added --\n"; html_body += "<br><b>-- Not Added --</b><br>"
            if unadded_plain:
                plain_body += "\n".join(unadded_plain); html_body += f"<ul>{''.join(unadded_html)}</ul>"
                total_unadded = sum(1 for s in lookup_results if s.get('id', 0) == 0); remaining = total_unadded - len(unadded_plain)
                if remaining > 0: more = f"\n... and {remaining} more."; plain_body += more; html_body += html.escape(more).replace('\n', '<br>')
            else:
                 total_added = sum(1 for s in lookup_results if s.get('id', 0) > 0); msg = ""
                 if len(lookup_results) > 0 and total_added == len(lookup_results): msg = "All matches are added."
                 else: msg = "None found."
                 plain_body += msg; html_body += f"{msg}<br>"

        # Call the generic formatted message sender
        await matrix_utils.send_formatted_message(bot, room.room_id, plain_body, html_body)

# --- Register Command ---
# ... (remains the same)
def register(bot: botlib.Bot, config_obj: config_module.MyConfig, prefix: str):
    async def handler_wrapper(room, message): await _sonarr_command_handler(room, message, bot, config_obj, prefix)
    bot.listener.on_message_event(handler_wrapper)
    logger.info("Sonarr command registered (handles search and info).")
