import logging
from aiohttp import web
import simplematrixbotlib as botlib
from . import config as config_module
from .utils import matrix_utils
from .services import radarr as radarr_service # <-- Import radarr_service

logger = logging.getLogger(__name__)

async def handle_radarr_webhook(request: web.Request):
    """Handles incoming webhook requests from Radarr."""
    try:
        bot: botlib.Bot = request.app['bot']
        config: config_module.MyConfig = request.app['config']

        if request.method != 'POST':
            logger.warning(f"Received non-POST request on webhook: {request.method}")
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
                # Optionally send a basic text notification here if desired
                await bot.api.send_text_message(config.target_room_id, f"✅ Downloaded: {movie_title_webhook} ({movie_data_from_webhook.get('year', 'N/A')}) - Release: {release_title}")
                return web.Response(status=200, text="Notification sent (basic text - missing ID)")

            logger.info(f"Processing Radarr 'Download' event for movie: '{movie_title_webhook}' (ID: {radarr_movie_id}), release: '{release_title}'. Fetching full details...")

            # --- Fetch full, current movie details using the ID ---
            full_movie_details = radarr_service.get_radarr_movie_details(
                radarr_movie_id,
                config.radarr_url,
                config.radarr_api_key
            )

            if not full_movie_details:
                logger.error(f"Failed to fetch full details for Radarr movie ID {radarr_movie_id} ('{movie_title_webhook}') after webhook trigger.")
                # Send a fallback notification
                await bot.api.send_text_message(config.target_room_id, f"✅ Downloaded: {movie_title_webhook} ({movie_data_from_webhook.get('year', 'N/A')}) - Release: {release_title} (Error fetching full details)")
                return web.Response(status=500, text="Failed to fetch full details from Radarr API")

            # --- Send Notification Card using FULL details ---
            logger.info(f"Sending notification card for '{full_movie_details.get('title', 'N/A')}' using full details.")
            await matrix_utils.send_media_info_card(
                bot=bot,
                room_id=config.target_room_id,
                media_data=full_movie_details, # Use the complete data from the API call
                is_added=True, # It's in Radarr if we got details by ID
                config=config,
                media_type='movie'
                # Add release title if desired (needs modification in send_media_info_card)
                # release_title=release_title
            )
            return web.Response(status=200, text="Notification sent (full details)")

        else:
            logger.debug(f"Ignoring Radarr webhook event type: {event_type}")
            return web.Response(status=200, text="Event type ignored")

    except Exception as e:
        logger.exception(f"Error handling Radarr webhook: {e}")
        return web.Response(status=500, text="Internal server error")

# setup_webhook_routes remains the same
def setup_webhook_routes(app: web.Application):
    app.router.add_post('/webhook/radarr', handle_radarr_webhook)
    logger.info("Registered Radarr webhook route: /webhook/radarr (POST)")