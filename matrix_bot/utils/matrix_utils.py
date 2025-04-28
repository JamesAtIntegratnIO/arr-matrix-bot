import logging
import re  # Import regular expressions for slugify
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# --- Slugify Function ---
def slugify(text):
    """
    Convert a string into a URL-friendly 'slug'.
    Lowercase, remove non-word characters (alphanumeric & underscore),
    replace whitespace with hyphens, and strip leading/trailing hyphens.
    """
    if not text:
        return ""
    text = text.lower()
    # Remove characters that aren't alphanumeric, underscores, whitespace, or hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace whitespace with hyphens
    text = re.sub(r'\s+', '-', text)
    # Replace multiple consecutive hyphens with a single one (optional, but good practice)
    text = re.sub(r'-{2,}', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text

# Helper function to safely get nested dictionary values
def get_nested(data: dict | list, *keys, default=None):
    """Safely retrieve a nested value from a dictionary or list."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return default
    return current

async def send_formatted_message(bot: botlib.Bot, room_id: str, plain_body: str, html_body: str):
    """Sends a message with plain text body and HTML formatted body."""
    try:
        content = {
            "msgtype": "m.text",
            "format": "org.matrix.custom.html",
            "body": plain_body,
            "formatted_body": html_body
        }
        
async def send_media_info_card(bot, room_id: str, media_data: dict, is_added: bool, config, media_type: str):
    """Sends a formatted card notification to Matrix."""

    if not media_data:
        logger.error("send_media_info_card called with empty media_data.")
        return

    event_type = get_nested(media_data, 'event_type', default='Download')

    # --- Determine Title, Year/Season/Episode, Overview ---
    title = "Unknown Title"
    year_or_episode = ""
    overview = get_nested(media_data, 'overview', default="No overview available.")
    tmdb_id = None
    tvdb_id = None
    imdb_id = None
    series_title_for_log = "" # For logging clarity

    if media_type == 'movie':
        title = get_nested(media_data, 'title', default=title)
        series_title_for_log = title
        year = get_nested(media_data, 'year')
        if year: year_or_episode = f" ({year})"
        tmdb_id = get_nested(media_data, 'tmdbId')
        imdb_id = get_nested(media_data, 'imdbId')
        logger.info(f"Constructing Radarr info card for '{title}'")

    elif media_type == 'episode':
        series_data = get_nested(media_data, 'series', default={})
        series_title = get_nested(series_data, 'title', default="Unknown Series")
        series_title_for_log = series_title

        episode_title = get_nested(media_data, 'title', default="Unknown Episode")
        season_num = get_nested(media_data, 'seasonNumber')
        episode_num = get_nested(media_data, 'episodeNumber')

        title = f"{series_title} - {episode_title}"
        if season_num is not None and episode_num is not None:
            year_or_episode = f" (S{season_num:02d}E{episode_num:02d})"

        tvdb_id = get_nested(series_data, 'tvdbId')
        tmdb_id = get_nested(series_data, 'tvdbId') # Often same as TVDB for series
        imdb_id = get_nested(series_data, 'imdbId')

        logger.info(f"Constructing Sonarr info card for '{series_title} S{season_num:02d}E{episode_num:02d}'")

    else:
        logger.error(f"Unsupported media_type '{media_type}' in send_media_info_card.")
        return


    # --- Determine Poster URL ---
    poster_url = None
    images = []
    base_url_for_relative_path = None

    if media_type == 'movie':
        images = get_nested(media_data, 'images', default=[])
        base_url_for_relative_path = config.radarr_url
    elif media_type == 'episode':
        series_data = get_nested(media_data, 'series', default={})
        images = get_nested(series_data, 'images', default=[])
        base_url_for_relative_path = config.sonarr_url

    for image in images:
        if isinstance(image, dict) and image.get('coverType') == 'poster':
            poster_url = image.get('remoteUrl') or image.get('url')
            if poster_url:
                if poster_url.startswith('/') and base_url_for_relative_path:
                    if not base_url_for_relative_path.startswith(('http://', 'https://')):
                         base_url_for_relative_path = 'http://' + base_url_for_relative_path
                    cleaned_base_url = base_url_for_relative_path.rstrip('/')
                    poster_url = cleaned_base_url + poster_url
                    logger.debug(f"Prepended base URL to relative poster URL: {poster_url}")
                elif poster_url.startswith('/') and not base_url_for_relative_path:
                     logger.warning(f"Poster URL '{poster_url}' looks relative, but base URL for {media_type} is not configured.")
                     poster_url = None

                if poster_url:
                     logger.info(f"Found poster URL: {poster_url}")
                     break

    if not poster_url:
        logger.info("No poster URL found.")


    # --- Construct Links (Using slug for Sonarr) ---
    links_html = ""
    # External links
    if tvdb_id and media_type == 'episode': links_html += f' <a href="https://thetvdb.com/?tab=series&id={tvdb_id}">TVDB</a>'
    if imdb_id: links_html += f' <a href="https://www.imdb.com/title/{imdb_id}/">IMDb</a>'

    # Add Sonarr/Radarr links
    arr_base_url = config.sonarr_url if media_type == 'episode' else config.radarr_url
    arr_link = None
    arr_name = "Sonarr" if media_type == 'episode' else "Radarr"

    if arr_base_url:
        # Ensure base URL has scheme and trailing slash for urljoin consistency
        if not arr_base_url.startswith(('http://', 'https://')):
            arr_base_url = 'http://' + arr_base_url
        cleaned_base_url = arr_base_url.rstrip('/') + '/'

        if media_type == 'episode':
            # *** Use slugified series title for Sonarr link ***
            series_title_for_slug = get_nested(media_data, 'series', 'title')
            series_id_fallback = get_nested(media_data, 'series', 'id') # Keep ID for fallback
            if series_title_for_slug:
                series_slug = slugify(series_title_for_slug)
                if series_slug:
                    arr_link = urljoin(cleaned_base_url, f'series/{series_slug}')
                    logger.debug(f"Generated Sonarr link using slug: {arr_link}")
                elif series_id_fallback: # Fallback to ID if slug is empty but ID exists
                     logger.warning(f"Could not generate valid slug for series '{series_title_for_slug}', falling back to ID link.")
                     arr_link = urljoin(cleaned_base_url, f'series/{series_id_fallback}')
            elif series_id_fallback: # Fallback if title is missing but ID exists
                logger.warning("Series title missing, falling back to ID link for Sonarr.")
                arr_link = urljoin(cleaned_base_url, f'series/{series_id_fallback}')
            # *** End Sonarr link change ***
        else: # Radarr (movie)
            movie_id = get_nested(media_data, 'id')
            if movie_id:
                 arr_link = urljoin(cleaned_base_url, f'movie/{movie_id}')
                 logger.debug(f"Generated Radarr link using ID: {arr_link}")

    # Add the constructed link to the HTML
    if arr_link:
        links_html += f' <a href="{arr_link}">{arr_name}</a>'


    # --- Construct Message Body ---
    status_emoji = "✅"
    if event_type == 'Download': status_text = "Downloaded"
    elif event_type == 'Grab': status_text = "Grabbed"
    else: status_text = "Processed"

    text_body = f"{status_emoji} {status_text}: {title}{year_or_episode}"
    release_title = get_nested(media_data, 'releaseTitle')
    if release_title: text_body += f" - Release: {release_title}"

    html_body = f"""
    <p>{status_emoji} <strong>{status_text}: {title}{year_or_episode}</strong></p>
    """
    if release_title: html_body += f"<p><em>Release:</em> {release_title}</p>"
    if poster_url: html_body += f'<p><img src="{poster_url}" alt="Poster Image" width="100" /></p>'
    if overview: html_body += f"<p>{overview}</p>"
    else: html_body += "<p>No overview available.</p>"
    if links_html: html_body += f"<p>Links:{links_html}</p>"


    # --- Send Message ---
    try:
        await bot.api.async_client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.notice",
                "body": text_body,
                "format": "org.matrix.custom.html",
                "formatted_body": html_body
            }
        )
        logger.info(f"Successfully sent notification card to room {room_id} for '{series_title_for_log}{year_or_episode}'.")
    except Exception as e:
        logger.error(f"Failed to send notification card to room {room_id}: {e}", exc_info=True)
