import logging
from aiohttp import web
import simplematrixbotlib as botlib
# Import necessary modules
from . import config as config_module
from .utils import matrix_utils
from .services import radarr as radarr_service
# --- ADD Sonarr service import (create services/sonarr.py if needed) ---
# from .services import sonarr as sonarr_service # Uncomment when ready

logger = logging.getLogger(__name__)

# --- Radarr Webhook Handler (handle_radarr_webhook remains unchanged) ---
async def handle_radarr_webhook(request: web.Request):
    # ... (keep existing Radarr handler code) ...
    try:
        bot: botlib.Bot = request.app['bot']
        config: config_module.MyConfig = request.app['config']

        if request.method != 'POST':
            logger.warning(f"Received non-POST request on Radarr webhook: {request.method}")
            return web.Response(status=405)

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
            # ... (existing Radarr Download logic) ...
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

            full_movie_details = radarr_service.get_radarr_movie_details(
                radarr_movie_id,
                config.radarr_url,
                config.radarr_api_key,
                # Assuming verify_tls is handled within the service function or passed if needed
                # verify_tls=config.verify_tls
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
                is_added=True, # Assuming it's added if we fetch by ID
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


# --- ADD Sonarr Webhook Handler ---
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
            release_title = release_data.get('title', 'N/A') if release_data else 'N/A' # Sonarr uses 'title' in release

            if not series_data or not episodes_data:
                logger.warning("Sonarr 'Download' event received, but missing 'series' or 'episodes' data.")
                return web.Response(status=400, text="Missing series or episodes data")

            series_title = series_data.get('title', 'N/A')
            series_id = series_data.get('id') # Useful for potential API calls

            logger.info(f"Processing Sonarr 'Download' event for series: '{series_title}' (ID: {series_id}), release: '{release_title}'.")

            # Process each episode in the download event
            notification_sent = False
            for episode in episodes_data:
                episode_id = episode.get('id')
                season_num = episode.get('seasonNumber')
                episode_num = episode.get('episodeNumber')
                episode_title = episode.get('title', 'N/A')

                if episode_id is None or season_num is None or episode_num is None:
                    logger.warning(f"Skipping episode in '{series_title}' due to missing ID/Season/Number in payload.")
                    continue

                logger.info(f"Processing episode S{season_num:02d}E{episode_num:02d} '{episode_title}' (ID: {episode_id}) for '{series_title}'.")

                # --- Placeholder for fetching full details (Optional but recommended) ---
                try:
                    full_episode_details = await sonarr_service.get_sonarr_episode_details(
                        episode_id, config.sonarr_url, config.sonarr_api_key #, verify_tls=config.verify_tls
                    )
                    if full_episode_details:
                         logger.info(f"Fetched full details for episode ID {episode_id}.")
                         # Use full_episode_details for the notification card
                         media_data_for_card = full_episode_details
                    else:
                         logger.warning(f"Failed to fetch full details for episode ID {episode_id}. Using webhook data.")
                         # Fallback to webhook data if API call fails
                         media_data_for_card = {
                             "title": series_title, # Card needs series title
                             "episodeTitle": episode_title,
                             "seasonNumber": season_num,
                             "episodeNumber": episode_num,
                             "id": episode_id, # Pass episode ID
                             "seriesId": series_id # Pass series ID
                             # Add other useful fields from webhook payload if needed
                         }
                except Exception as api_err:
                     logger.error(f"Error fetching Sonarr details for episode ID {episode_id}: {api_err}")
                     # Fallback to webhook data on error
                     media_data_for_card = { ... } # Same fallback as above

                # --- Use webhook data directly for now ---
                media_data_for_card = {
                    "title": series_title, # Pass series title
                    "episodeTitle": episode_title,
                    "seasonNumber": season_num,
                    "episodeNumber": episode_num,
                    "id": episode_id, # Pass episode ID
                    "seriesId": series_id, # Pass series ID
                    "releaseTitle": release_title # Pass release title if you want to display it
                    # Add other useful fields from webhook payload if needed
                }
                # -----------------------------------------

                # --- Send Notification Card ---
                try:
                    logger.info(f"Sending notification card for {series_title} S{season_num:02d}E{episode_num:02d}.")
                    await matrix_utils.send_media_info_card(
                        bot=bot,
                        room_id=config.target_room_id,
                        media_data=media_data_for_card,
                        is_added=True, # Assuming it's in Sonarr if downloaded
                        config=config,
                        media_type='episode' # <-- Specify episode type
                    )
                    notification_sent = True
                except Exception as matrix_err:
                    logger.error(f"Failed to send Matrix notification for episode ID {episode_id}: {matrix_err}")

            if notification_sent:
                return web.Response(status=200, text="Notification(s) sent")
            else:
                logger.warning(f"Finished processing Sonarr download for '{series_title}', but no valid episodes found or notifications sent.")
                return web.Response(status=200, text="Processed, but no notifications sent (check episode data)")

        else:
            logger.debug(f"Ignoring Sonarr webhook event type: {event_type}")
            return web.Response(status=200, text="Event type ignored")

    except Exception as e:
        logger.exception(f"Error handling Sonarr webhook: {e}")
        return web.Response(status=500, text="Internal server error")


# --- Route Setup Function (Simplified as per last step) ---
def setup_webhook_routes(app: web.Application):
    """Registers ONLY the application-specific webhook routes."""
    # Radarr Route (from previous state)
    app.router.add_post('/webhook/radarr', handle_radarr_webhook)
    logger.info("Registered Radarr webhook route: /webhook/radarr (POST)")

    # --- ADD Sonarr Route ---
    # app.router.add_post('/webhook/sonarr', handle_sonarr_webhook) # Route added in __main__.py now
    # logger.info("Registered Sonarr webhook route: /webhook/sonarr (POST)") # Logged in __main__.py