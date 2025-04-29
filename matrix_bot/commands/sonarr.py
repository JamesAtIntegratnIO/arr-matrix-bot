import logging
import simplematrixbotlib as botlib
from nio import RoomMessageText, MatrixRoom, RoomSendResponse, RoomSendError
from .. import config as config_module
from ..services import sonarr as sonarr_service
from ..utils import matrix_utils # Keep for send_media_info_card
import html
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

UNADDED_ONLY_FLAG = "--unadded"
COMMAND_NAME = "sonarr"

# --- Help Registration ---
def register_help(help_registry: Dict[str, Dict[str, str]], prefix: str):
    """Registers the help text for the sonarr command."""
    command_key = COMMAND_NAME # e.g., "sonarr"

    # Define description and usage separately
    description = "Searches Sonarr for TV series or gets info about a specific series."
    usage = (
        f"{prefix}{COMMAND_NAME} [search] [--unadded] <search_term>\n"
        f"  Searches for series. Use `--unadded` to show only results not yet in Sonarr.\n\n"
        f"{prefix}{COMMAND_NAME} info <tvdb_id>\n"
        f"  Gets detailed info and poster for a specific series using its TVDb ID."
    )

    # Assign a DICTIONARY to the registry
    help_registry[command_key] = {
        "description": description,
        "usage": usage
    }
    logger.debug(f"Registered help for command: {command_key}")


# --- Handler: Process 'info' Subcommand (Uses Generic Card Sender) ---
async def _handle_sonarr_info(tvdb_id: int, room: MatrixRoom, bot: botlib.Bot, config: config_module.MyConfig):
    logger.info(f"Handling sonarr info request for TVDb ID: {tvdb_id}")
    lookup_query = f"tvdb:{tvdb_id}"
    # *** FIX: Add await and verify_tls ***
    lookup_results = await sonarr_service.search_sonarr_lookup(
        lookup_query, config.sonarr_url, config.sonarr_api_key, verify_tls=config.verify_tls
    )
    # *** END FIX ***
    if lookup_results is None: await bot.api.send_text_message(room.room_id, f"Error: Could not communicate with Sonarr API while looking up TVDb ID {tvdb_id}."); return
    if not lookup_results: await bot.api.send_text_message(room.room_id, f"Sonarr could not find any series matching TVDb ID {tvdb_id}."); return

    # Assume the first result is the most relevant for direct ID lookup
    series_lookup_data = lookup_results[0]
    series_id = series_lookup_data.get('id', 0)
    # Sonarr lookup might return 0 for ID if not added, check 'tvdbId' exists and matches requested
    is_added = series_id > 0 and series_lookup_data.get('tvdbId') == tvdb_id

    data_for_card = None
    tvdb_id_from_lookup = series_lookup_data.get('tvdbId') # Get ID from result

    if is_added:
        logger.info(f"TVDb ID {tvdb_id} found in Sonarr with ID {series_id}. Fetching details.")
        # *** FIX: Add await and verify_tls ***
        details = await sonarr_service.get_sonarr_series_details(
            series_id, config.sonarr_url, config.sonarr_api_key, verify_tls=config.verify_tls
        )
        # *** END FIX ***
        if not details: await bot.api.send_text_message(room.room_id, f"Found series with TVDb ID {tvdb_id} in Sonarr, but failed to fetch its details."); return
        # Ensure TVDb ID is present for the card function
        if 'tvdbId' not in details: details['tvdbId'] = tvdb_id
        data_for_card = details
    else:
        logger.info(f"TVDb ID {tvdb_id} found via lookup, but not added to Sonarr.")
        # Ensure TVDb ID is present for the card function
        if 'tvdbId' not in series_lookup_data: series_lookup_data['tvdbId'] = tvdb_id
        data_for_card = series_lookup_data # Use lookup data directly for unadded

    if data_for_card:
        # Pass tvdb_id explicitly if needed by card function, or ensure it's in data_for_card
        await matrix_utils.send_media_info_card(
            bot=bot, room_id=room.room_id, media_data=data_for_card,
            is_added=is_added, config=config, media_type='series' # Use 'series' type
        )
    else:
        logger.error("Failed to prepare data for Sonarr info card."); await bot.api.send_text_message(room.room_id, "An internal error occurred preparing card data.")


# --- Main Command Handler ---
async def _sonarr_command_handler(room: MatrixRoom, message: RoomMessageText, bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
    if message.sender == config.matrix_user: return

    full_command = prefix + COMMAND_NAME
    usage_string = f"""Usage:\n  `{prefix}{COMMAND_NAME} [search] [{UNADDED_ONLY_FLAG}] <search_term>`\n  `{prefix}{COMMAND_NAME} info <tvdb_id>`"""
    if not message.body.startswith(full_command): return
    args_part = message.body[len(full_command):].strip(); args = args_part.split()
    if not args: await bot.api.send_text_message(room.room_id, usage_string); return

    # --- Handle 'info' subcommand ---
    if args[0].lower() == "info":
        if len(args) != 2: await bot.api.send_text_message(room.room_id, f"Usage: `{prefix}{COMMAND_NAME} info <tvdb_id>`"); return
        try:
            tvdb_id_arg = int(args[1]);
            if tvdb_id_arg <= 0: raise ValueError("TVDb ID must be positive.")
            if not config.sonarr_url or not config.sonarr_api_key: await bot.api.send_text_message(room.room_id, "Error: Sonarr is not configured."); return
            await _handle_sonarr_info(tvdb_id_arg, room, bot, config) # Call the dedicated info handler
            return
        except ValueError: await bot.api.send_text_message(room.room_id, f"Invalid TVDb ID. Usage: `{prefix}{COMMAND_NAME} info <tvdb_id>`"); return
        except Exception as e:
            logger.error(f"Error processing 'sonarr info {args[1]}': {e}", exc_info=True)
            await bot.api.send_text_message(room.room_id, "An unexpected error occurred while handling the info command.")
            return

    # --- Search Logic ---
    show_unadded_only = False; search_term_words = []; args_copy = list(args)
    if UNADDED_ONLY_FLAG in args_copy: show_unadded_only = True; args_copy.remove(UNADDED_ONLY_FLAG)
    # Allow 'search' keyword optionally
    if args_copy and args_copy[0].lower() == "search": search_term_words = args_copy[1:]
    else: search_term_words = args_copy # Assume remaining args are the search term
    if not search_term_words: await bot.api.send_text_message(room.room_id, usage_string); return
    search_term = " ".join(search_term_words)

    if not config.sonarr_url or not config.sonarr_api_key: await bot.api.send_text_message(room.room_id, "Error: Sonarr is not configured."); return

    logger.info(f"Received sonarr search command from {message.sender} (Unadded: {show_unadded_only}) for: '{search_term}'")

    # *** FIX: Add await and verify_tls ***
    lookup_results = await sonarr_service.search_sonarr_lookup(
        search_term, config.sonarr_url, config.sonarr_api_key, verify_tls=config.verify_tls
    )
    # *** END FIX ***

    if lookup_results is None: await bot.api.send_text_message(room.room_id, "Error: Sonarr API communication failed."); return
    elif not lookup_results: await bot.api.send_text_message(room.room_id, f"No series found matching '{search_term}'."); return
    else:
        # --- Build Search Results List ---
        added_plain = []; added_html = []; unadded_plain = []; unadded_html = []
        max_unadded = float('inf') if show_unadded_only else 5
        processed_count = 0

        # *** Wrap iteration in try...except as lookup_results might not be iterable on error ***
        try:
            for series_lookup_data in lookup_results:
                processed_count += 1
                title = series_lookup_data.get('title', 'N/A')
                year = series_lookup_data.get('year', 'N/A')
                tvdb_id = series_lookup_data.get('tvdbId', 'N/A')
                # Check 'id' field; Sonarr V3 often returns 0 if not added, V4 might use 'sonarrId' or similar
                series_id = series_lookup_data.get('id', 0) # Check if 'id' exists and is > 0
                is_added = series_id > 0
                season_count_lookup = series_lookup_data.get('seasonCount', 0)

                line_base = f"{html.escape(title)} ({year}) [TVDb: {tvdb_id}]"

                if is_added:
                    if not show_unadded_only:
                        # *** FIX: Add await and verify_tls ***
                        details = await sonarr_service.get_sonarr_series_details(
                            series_id, config.sonarr_url, config.sonarr_api_key, verify_tls=config.verify_tls
                        )
                        # *** END FIX ***
                        season_count = season_count_lookup; status = 'N/A'; monitored = False
                        if details:
                            seasons_list = details.get('seasons', [])
                            stats = details.get('statistics', {})
                            # Prefer season count from details if available
                            season_count = len(seasons_list) if seasons_list else stats.get('seasonCount', season_count_lookup)
                            status = details.get('status', 'N/A')
                            monitored = details.get('monitored', False)
                        else: logger.warning(f"Could not fetch details for added series ID {series_id} ('{title}') during search list build.")

                        status_ind = ""; status_ind_h = ""
                        if monitored: status_ind = " (Monitored)"; status_ind_h = " (Monitored)"
                        elif status != 'ended': status_ind = f" ({status.capitalize()})"; status_ind_h = f" ({html.escape(status.capitalize())})"

                        added_plain.append(f"- {line_base} - {season_count} seasons{status_ind}")
                        added_html.append(f"<li>{line_base} - {season_count} seasons{status_ind_h}</li>")
                else: # Not added
                    if len(unadded_plain) < max_unadded:
                        unadded_plain.append(f"- {line_base} - {season_count_lookup} seasons")
                        unadded_html.append(f"<li>{line_base} - {season_count_lookup} seasons</li>")

        except TypeError as te:
             # Catch the specific error if lookup_results wasn't iterable after all
             logger.error(f"Error iterating Sonarr lookup results: {te}. Results: {lookup_results}", exc_info=True)
             await bot.api.send_text_message(room.room_id, "Error processing Sonarr results. Check logs.")
             return
        except Exception as e:
             logger.error(f"Unexpected error processing Sonarr search results: {e}", exc_info=True)
             await bot.api.send_text_message(room.room_id, "An unexpected error occurred processing search results.")
             return


        # --- Format Body ---
        plain_body = ""; html_body = ""; search_term_esc = html.escape(search_term)
        total_unadded_count = sum(1 for s in lookup_results if s.get('id', 0) == 0)

        if show_unadded_only:
            plain_body = f"Sonarr results for '{search_term}' (Not Added Only):\n\n"
            html_body = f"<p>Sonarr results for '<i>{search_term_esc}</i>' (Not Added Only):</p>"
            if unadded_plain:
                 plain_body += "\n".join(unadded_plain)
                 html_body += f"<ul>{''.join(unadded_html)}</ul>"
                 if len(unadded_plain) < total_unadded_count:
                     more = f"\n... and {total_unadded_count - len(unadded_plain)} more."
                     plain_body += more
                     html_body += f"<p>{html.escape(more).replace(chr(10), '<br>')}</p>" # Use chr(10) for newline
            else:
                 plain_body += "No unadded series found."; html_body += "<p>No unadded series found.</p>"
        else:
            plain_body = f"Sonarr results for '{search_term}':\n\n"
            html_body = f"<p>Sonarr results for '<i>{search_term_esc}</i>':</p>"
            plain_body += "-- Added --\n"; html_body += "<p><b>-- Added --</b></p>"
            if added_plain: plain_body += "\n".join(added_plain); html_body += f"<ul>{''.join(added_html)}</ul>"
            else: plain_body += "None found."; html_body += "<p>None found.</p>"

            plain_body += "\n\n-- Not Added --\n"; html_body += "<p><b>-- Not Added --</b></p>"
            if unadded_plain:
                plain_body += "\n".join(unadded_plain)
                html_body += f"<ul>{''.join(unadded_html)}</ul>"
                remaining_unadded = total_unadded_count - len(unadded_plain)
                if remaining_unadded > 0:
                    more = f"\n... and {remaining_unadded} more."
                    plain_body += more
                    html_body += f"<p>{html.escape(more).replace(chr(10), '<br>')}</p>" # Use chr(10) for newline
            else:
                 total_added_count = sum(1 for s in lookup_results if s.get('id', 0) > 0)
                 msg = ""
                 if processed_count > 0 and total_added_count == processed_count: msg = "All matches are added."
                 else: msg = "None found."
                 plain_body += msg; html_body += f"<p>{msg}</p>"

        # *** FIX: Send using room_send directly ***
        try:
            await bot.api.async_client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.notice", # Use notice for bot messages
                    "body": plain_body,
                    "format": "org.matrix.custom.html",
                    "formatted_body": html_body
                }
            )
        except Exception as send_err:
            logger.error(f"Failed to send Sonarr search results to room {room.room_id}: {send_err}", exc_info=True)
            # Optionally try sending plain text as fallback
            try:
                await bot.api.send_text_message(room.room_id, plain_body)
            except Exception as fallback_err:
                 logger.error(f"Failed to send fallback plain text message for Sonarr search: {fallback_err}")
        # *** END FIX ***

# *** FIX: De-indent the register function ***
# --- Register Command ---
def register(bot: botlib.Bot, config_obj: config_module.MyConfig, prefix: str):
    """Registers the sonarr command handler with the bot."""
    # Create a closure to capture bot, config_obj, and prefix
    async def handler_wrapper(room, message):
        # Add a top-level try-except within the handler wrapper for safety
        try:
            await _sonarr_command_handler(room, message, bot, config_obj, prefix)
        except Exception as handler_exc:
            logger.error(f"Unhandled exception in _sonarr_command_handler: {handler_exc}", exc_info=True)
            try:
                # Attempt to notify the room about the internal error
                await bot.api.send_text_message(room.room_id, "Sorry, an internal error occurred while processing the sonarr command.")
            except Exception as report_exc:
                logger.error(f"Failed to report internal handler error to room {room.room_id}: {report_exc}")

    bot.listener.on_message_event(handler_wrapper)
    logger.info("Sonarr command registered (handles search and info).")
# *** END FIX ***