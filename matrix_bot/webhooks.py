import logging
from aiohttp import web
import simplematrixbotlib as botlib
# Import necessary modules
from . import config as config_module
from .utils import matrix_utils
from .services import radarr as radarr_service
# --- Ensure Sonarr service is imported ---
from .services import sonarr as sonarr_service

logger = logging.getLogger(__name__)

# --- Radarr Webhook Handler (handle_radarr_webhook remains unchanged) ---
async def handle_radarr_webhook(request: web.Request):
    # ... (existing Radarr handler code) ...
    # (Code omitted for brevity, assuming it's correct from previous steps)
    try:
        bot: botlib.Bot = request.app['bot']
        config: config_module.MyConfig = request.app['config']

        if request.method != 'POST':
            logger.warning(f"Received non-POST request on Radarr webhook: {request.method}")
            return web.Response(status=405) # Method Not Allowed

        payload = await request.json()
        event_type = payload.get('eventType')
        logger.info(f"Received Radarr webhook. Event type: {event_type}")

        if event_type == 'Test':
            logger.info("Received Radarr 'Test' webhook successfully.")
            try:
                await bot.api.send_text_message(config.target_room_id, "✅ Received Radarr 'Test' webhook successfully!")
            except Exception as e:
                logger.error(f"Failed to send Radarr test confirmation to room: {e}")
            return web.Response(status=200, text="Test webhook received")

        if event_type == 'Download':
            movie_data_from_webhook = payload.get('movie')
            release_data = payload.get('release')
            release_title = release_data.get('releaseTitle', 'N/A') if release_data else 'N/A'

            if not movie_data_from_webhook:
                logger.warning("Radarr 'Download' event received, but no 'movie' data found in payload.")
                return web.Response(status=400, text="Missing movie data")

            radarr_movie_id = movie_data_from_webhook.get('id')
            movie_title_webhook = movie_data_from_webhook.get('title', 'N/A')

            if not radarr_movie_id:
                logger.warning(f"Radarr 'Download' event for '{movie_title_webhook}' missing movie ID in payload. Cannot fetch full details.")
                await bot.api.send_text_message(config.target_room_id, f"✅ Downloaded: {movie_title_webhook} ({movie_data_from_webhook.get('year', 'N/A')}) - Release: {release_title}")
                return web.Response(status=200, text="Notification sent (basic text - missing ID)")

            logger.info(f"Processing Radarr 'Download' event for movie: '{movie_title_webhook}' (ID: {radarr_movie_id}), release: '{release_title}'. Fetching full details...")

            full_movie_details = await radarr_service.get_radarr_movie_details( # Assuming this service function is async now
                radarr_movie_id,
                config.radarr_url,
                config.radarr_api_key,
                verify_tls=config.verify_tls # Pass verify_tls setting
            )

            if not full_movie_details:
                logger.error(f"Failed to fetch full details for Radarr movie ID {radarr_movie_id} ('{movie_title_webhook}') after webhook trigger.")
                await bot.api.send_text_message(config.target_room_id, f"✅ Downloaded: {movie_title_webhook} ({movie_data_from_webhook.get('year', 'N/A')}) - Release: {release_title} (Error fetching full details)")
                return web.Response(status=500, text="Failed to fetch full details from Radarr API")

            logger.info(f"Sending notification card for '{full_movie_details.get('title', 'N/A')}' using full details.")
            await matrix_utils.send_media_info_card(
                bot=bot,
                room_id=config.target_room_id,
                media_data=full_movie_details,
                is_added=True,
                config=config,
                media_type='movie'
            )
            return web.Response(status=200, text="Notification sent (full details)")

        else:
            logger.debug(f"Ignoring Radarr webhook event type: {event_type}")
            return web.Response(status=200, text="Event type ignored")

    except Exception as e:
        logger.exception(f"Error handling Radarr webhook: {e}")
        return web.Response(status=500, text="Internal server error")


# --- Sonarr Webhook Handler (Updated with API Call) ---
async def handle_sonarr_webhook(request: web.Request):
    """Handles incoming webhook requests from Sonarr."""
    try:
        bot: botlib.Bot = request.app['bot']
        config: config_module.MyConfig = request.app['config']

        if request.method != 'POST':
            logger.warning(f"Received non-POST request on Sonarr webhook: {request.method}")
            return web.Response(status=405) # Method Not Allowed

        payload = await request.json()
        event_type = payload.get('eventType')
        logger.info(f"Received Sonarr webhook. Event type: {event_type}")

        # --- Handle Test Event ---
        if event_type == 'Test':
            logger.info("Received Sonarr 'Test' webhook successfully.")
            try:
                await bot.api.send_text_message(config.target_room_id, "✅ Received Sonarr 'Test' webhook successfully!")
            except Exception as e:
                logger.error(f"Failed to send Sonarr test confirmation to room: {e}")
            return web.Response(status=200, text="Test webhook received")

        # --- Handle Download Event ---
        if event_type == 'Download':
            series_data = payload.get('series')
            episodes_data = payload.get('episodes') # Sonarr sends a list of episodes
            release_data = payload.get('release')
            release_title = release_data.get('title', 'N/A') if release_data else 'N/A'

            if not series_data or not episodes_data:
                logger.warning("Sonarr 'Download' event received, but missing 'series' or 'episodes' data.")
                return web.Response(status=400, text="Missing series or episodes data")

            series_title_webhook = series_data.get('title', 'N/A') # Get title from webhook as fallback
            series_id = series_data.get('id')

            logger.info(f"Processing Sonarr 'Download' event for series: '{series_title_webhook}' (ID: {series_id}), release: '{release_title}'.")

            notification_sent = False
            for episode in episodes_data:
                episode_id = episode.get('id')
                season_num_webhook = episode.get('seasonNumber') # Get from webhook as fallback
                episode_num_webhook = episode.get('episodeNumber') # Get from webhook as fallback
                episode_title_webhook = episode.get('title', 'N/A') # Get from webhook as fallback

                if episode_id is None or season_num_webhook is None or episode_num_webhook is None:
                    logger.warning(f"Skipping episode in '{series_title_webhook}' due to missing ID/Season/Number in payload.")
                    continue

                logger.info(f"Processing episode S{season_num_webhook:02d}E{episode_num_webhook:02d} '{episode_title_webhook}' (ID: {episode_id}) for '{series_title_webhook}'.")

                # --- Fetch full details using sonarr_service ---
                media_data_for_card = None
                try:
                    # Assuming get_sonarr_episode_details is an async function
                    full_episode_details = await sonarr_service.get_sonarr_episode_details(
                        episode_id=episode_id,
                        sonarr_url=config.sonarr_url,
                        api_key=config.sonarr_api_key,
                        verify_tls=config.verify_tls # Pass verify_tls setting
                    )
                    if full_episode_details:
                        logger.info(f"Fetched full details for episode ID {episode_id} ('{full_episode_details.get('title', 'N/A')}') from Sonarr API.")
                        # Add release title if you want it in the card and the service doesn't provide it
                        full_episode_details['releaseTitle'] = release_title
                        media_data_for_card = full_episode_details
                    else:
                        logger.warning(f"Failed to fetch full details for episode ID {episode_id} from Sonarr API. Using webhook data as fallback.")
                except Exception as api_err:
                    logger.error(f"Error fetching Sonarr details for episode ID {episode_id}: {api_err}", exc_info=True)
                    # Fallback handled below

                # --- Fallback to webhook data if API call failed or returned None ---
                if not media_data_for_card:
                    logger.info(f"Using fallback data from webhook for episode ID {episode_id}.")
                    media_data_for_card = {
                        "title": series_title_webhook, # Use series title from webhook
                        "episodeTitle": episode_title_webhook,
                        "seasonNumber": season_num_webhook,
                        "episodeNumber": episode_num_webhook,
                        "id": episode_id, # Episode ID
                        "seriesId": series_id, # Series ID
                        "releaseTitle": release_title, # Release title from webhook
                        # Mark that this is fallback data, might be useful for card formatting
                        "is_fallback": True
                    }
                # --------------------------------------------------------------------

                # --- Send Notification Card ---
                try:
                    # Use the title from the fetched/fallback data for logging
                    log_series_title = media_data_for_card.get('series', {}).get('title') if not media_data_for_card.get('is_fallback') else media_data_for_card.get('title', 'N/A')
                    log_ep_title = media_data_for_card.get('title', 'N/A') if not media_data_for_card.get('is_fallback') else media_data_for_card.get('episodeTitle', 'N/A')
                    log_season = media_data_for_card.get('seasonNumber', '??')
                    log_episode = media_data_for_card.get('episodeNumber', '??')

                    logger.info(f"Sending notification card for {log_series_title} S{log_season:02d}E{log_episode:02d} ('{log_ep_title}').")

                    await matrix_utils.send_media_info_card(
                        bot=bot,
                        room_id=config.target_room_id,
                        media_data=media_data_for_card, # Use the data fetched or the fallback
                        is_added=True, # Assuming it's in Sonarr if downloaded
                        config=config,
                        media_type='episode' # Specify episode type
                    )
                    notification_sent = True
                except Exception as matrix_err:
                    logger.error(f"Failed to send Matrix notification for episode ID {episode_id}: {matrix_err}", exc_info=True)

            if notification_sent:
                return web.Response(status=200, text="Notification(s) sent")
            else:
                logger.warning(f"Finished processing Sonarr download for '{series_title_webhook}', but no valid episodes found or notifications sent.")
                return web.Response(status=200, text="Processed, but no notifications sent (check episode data)")

        else:
            logger.debug(f"Ignoring Sonarr webhook event type: {event_type}")
            return web.Response(status=200, text="Event type ignored")

    except Exception as e:
        logger.exception(f"Error handling Sonarr webhook: {e}")
        return web.Response(status=500, text="Internal server error")


# --- Route Setup Function (remains unchanged, routes added in __main__.py) ---
def setup_webhook_routes(app: web.Application):
    """Defines handlers, but routes are added in __main__.py."""
    pass