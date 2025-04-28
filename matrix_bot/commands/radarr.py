import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom, RoomSendResponse, RoomSendError # Keep RoomSendError if used elsewhere
from .. import config as config_module
from ..services import radarr as radarr_service
from ..utils import matrix_utils # Import the generic senders
import html
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

UNADDED_ONLY_FLAG = "--unadded"

# _send_formatted_message removed

# --- Handler for 'info' Subcommand (Uses Generic Card Sender) ---
# ... (remains the same, already calls matrix_utils.send_media_info_card)
async def _handle_radarr_info(tmdb_id: int, room: MatrixRoom, bot: botlib.Bot, config: config_module.MyConfig):
    logger.info(f"Handling radarr info request for TMDb ID: {tmdb_id}")
    lookup_result = radarr_service.lookup_radarr_movie_by_tmdb(tmdb_id, config.radarr_url, config.radarr_api_key)
    if lookup_result is None: await bot.api.send_text_message(room.room_id, f"Error: Could not communicate with Radarr API while looking up TMDb ID {tmdb_id}."); return
    elif not lookup_result: await bot.api.send_text_message(room.room_id, f"Radarr could not find any movie matching TMDb ID {tmdb_id}."); return
    radarr_movie_id = lookup_result.get('id', 0); is_added = radarr_movie_id > 0
    data_for_card = None; tmdb_id_from_lookup = lookup_result.get('tmdbId')
    if is_added:
        logger.info(f"TMDb ID {tmdb_id_from_lookup or tmdb_id} found in Radarr with ID {radarr_movie_id}. Fetching details.")
        details = radarr_service.get_radarr_movie_details(radarr_movie_id, config.radarr_url, config.radarr_api_key)
        if not details: await bot.api.send_text_message(room.room_id, f"Found movie with TMDb ID {tmdb_id_from_lookup or tmdb_id} in Radarr, but failed to fetch its details."); return
        if 'tmdbId' not in details and tmdb_id_from_lookup: details['tmdbId'] = tmdb_id_from_lookup
        elif 'tmdbId' not in details: details['tmdbId'] = tmdb_id
        data_for_card = details
    else:
        logger.info(f"TMDb ID {tmdb_id_from_lookup or tmdb_id} found via lookup, but not added to Radarr.")
        if 'tmdbId' not in lookup_result and tmdb_id_from_lookup: lookup_result['tmdbId'] = tmdb_id_from_lookup
        elif 'tmdbId' not in lookup_result: lookup_result['tmdbId'] = tmdb_id
        data_for_card = lookup_result
    if data_for_card:
        await matrix_utils.send_media_info_card(bot=bot, room_id=room.room_id, media_data=data_for_card, is_added=is_added, config=config, media_type='movie')
    else:
        logger.error("Failed to prepare data for Radarr info card."); await bot.api.send_text_message(room.room_id, "An internal error occurred.")

# --- Main Command Handler (Uses Generic Formatted Sender for Search) ---
async def _radarr_command_handler(room: MatrixRoom, message: RoomMessageText, bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
     # --- Ignore messages from the bot itself ---
    if message.sender == config.matrix_user:
        return
    # -------------------------------------------
    command_name = "radarr"; full_command = prefix + command_name
    usage_string = f"""Usage:
  `{prefix}{command_name} [search] [{UNADDED_ONLY_FLAG}] <search_term>`
  `{prefix}{command_name} info <tmdb_id>`"""
    if not message.body.startswith(full_command): return
    args_part = message.body[len(full_command):].strip(); args = args_part.split()
    if not args: await bot.api.send_text_message(room.room_id, usage_string); return

    if args[0].lower() == "info":
        # ... (info handling remains the same, calls _handle_radarr_info) ...
        if len(args) != 2: await bot.api.send_text_message(room.room_id, f"Usage: `{prefix}{command_name} info <tmdb_id>`"); return
        try:
            tmdb_id_arg = int(args[1]);
            if tmdb_id_arg <= 0: raise ValueError("TMDb ID must be positive.")
            if not config.radarr_url or not config.radarr_api_key: await bot.api.send_text_message(room.room_id, "Error: Radarr is not configured."); return
            await _handle_radarr_info(tmdb_id_arg, room, bot, config)
            return
        except ValueError: await bot.api.send_text_message(room.room_id, f"Invalid TMDb ID. Usage: `{prefix}{command_name} info <tmdb_id>`"); return

    # --- Search Logic ---
    show_unadded_only = False; search_term_words = []; args_copy = list(args)
    if UNADDED_ONLY_FLAG in args_copy: show_unadded_only = True; args_copy.remove(UNADDED_ONLY_FLAG)
    if args_copy and args_copy[0].lower() == "search": search_term_words = args_copy[1:]
    else: search_term_words = args_copy
    if not search_term_words: await bot.api.send_text_message(room.room_id, usage_string); return
    search_term = " ".join(search_term_words)
    if not config.radarr_url or not config.radarr_api_key: await bot.api.send_text_message(room.room_id, "Error: Radarr is not configured."); return
    logger.info(f"Received radarr search command from {message.sender} (Unadded: {show_unadded_only}) for: '{search_term}'")
    results = radarr_service.search_radarr_movie(search_term, config.radarr_url, config.radarr_api_key)

    if results is None: await bot.api.send_text_message(room.room_id, "Error: Radarr API communication failed."); return
    elif not results: await bot.api.send_text_message(room.room_id, f"No movies found matching '{search_term}'."); return
    else:
        # --- Build Search Results List ---
        added_movies = []; unadded_movies = []
        max_unadded_to_show = float('inf') if show_unadded_only else 5
        for movie in results:
            # ... (logic to populate added/unadded lists remains the same) ...
            title = movie.get('title', 'N/A'); year = movie.get('year', 'N/A'); tmdb_id = movie.get('tmdbId', 'N/A')
            is_added = movie.get('id', 0) > 0
            if is_added:
                if not show_unadded_only:
                    status = movie.get('status', 'N/A'); monitored = movie.get('monitored', False); has_file = movie.get('hasFile', False)
                    status_indicator = ""
                    if has_file: status_indicator = " (Downloaded)"
                    elif monitored: status_indicator = " (Monitored)"
                    elif status != 'released': status_indicator = f" ({status.capitalize()})"
                    added_movies.append(f"- {title} ({year}) [TMDb: {tmdb_id}]{status_indicator}")
            else:
                if len(unadded_movies) < max_unadded_to_show: unadded_movies.append(f"- {title} ({year}) [TMDb: {tmdb_id}]")

        # --- Format Body (Using Markdown for Radarr Search) ---
        # Note: Radarr search still uses plain text/markdown, not HTML list like Sonarr yet.
        response_message = ""; search_term_md = search_term.replace('_', r'\_').replace('*', r'\*')
        if show_unadded_only:
            response_message = f"Radarr results for '{search_term_md}' (Not Yet Added Only):\n\n"
            if unadded_movies:
                 response_message += "\n".join(unadded_movies)
                 total_unadded_count = sum(1 for m in results if m.get('id', 0) == 0)
                 if len(unadded_movies) < total_unadded_count: response_message += f"\n... and {total_unadded_count - len(unadded_movies)} more."
            else: response_message += "No unadded movies found."
        else:
            response_message = f"Radarr results for '{search_term_md}':\n\n"
            response_message += "**-- Already Added --**\n"
            if added_movies: response_message += "\n".join(added_movies)
            else: response_message += "None found."
            response_message += "\n\n**-- Not Yet Added --**\n"
            if unadded_movies:
                response_message += "\n".join(unadded_movies)
                total_unadded_count = sum(1 for m in results if m.get('id', 0) == 0)
                remaining_unadded = total_unadded_count - len(unadded_movies)
                if remaining_unadded > 0: response_message += f"\n... and {remaining_unadded} more."
            else:
                 total_added_count = sum(1 for m in results if m.get('id', 0) > 0)
                 if len(results) > 0 and total_added_count == len(results): response_message += "All matches found are added."
                 else: response_message += "None found."

        # Send plain text message for search results
        # If you want HTML lists for Radarr search too, you'd build html_body here
        # and call matrix_utils.send_formatted_message instead.
        await bot.api.send_text_message(room.room_id, response_message)

# --- Register Command ---
# ... (remains the same)
def register(bot: botlib.Bot, config_obj: config_module.MyConfig, prefix: str):
    async def handler_wrapper(room, message): await _radarr_command_handler(room, message, bot, config_obj, prefix)
    bot.listener.on_message_event(handler_wrapper)
    logger.info("Radarr command registered (handles search and info).")
