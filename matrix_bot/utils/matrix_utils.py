import logging
import re           # For slugify
import asyncio      # For image upload helper
import requests     # For image download helper
import io           # For image upload helper
import os           # For image upload helper
import html         # For escaping in old card sender (if kept/adapted) or help
from urllib.parse import urljoin
import simplematrixbotlib as botlib # For type hints if needed
from nio import AsyncClient, UploadResponse, RoomSendResponse, RoomSendError # For upload/send helpers
from typing import Optional, Dict, Any, List
# Import config only if needed directly in helpers (e.g., verify_tls)
from .. import config as config_module
# tvdb_utils might be needed if you re-introduce TVDB lookups, otherwise remove
# from . import tvdb as tvdb_utils

logger = logging.getLogger(__name__)

# --- Byte Formatting Helper (from Old Code) ---
def _format_bytes(size_bytes: int) -> str:
    """Formats bytes into a human-readable string (KB, MB, GB, TB)."""
    if not isinstance(size_bytes, (int, float)) or size_bytes < 0: return "N/A"
    if size_bytes < 1024: return f"{size_bytes} B"
    elif size_bytes < 1024**2: return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024**3: return f"{size_bytes/1024**2:.2f} MB"
    elif size_bytes < 1024**4: return f"{size_bytes/1024**3:.2f} GB"
    else: return f"{size_bytes/1024**4:.2f} TB"

# --- Image Download Helper (Sync - from Old Code) ---
# Runs in a separate thread via upload_image_to_matrix
def _sync_download_image(image_url: str, config: config_module.MyConfig) -> Optional[Dict[str, Any]]:
    """Synchronously downloads an image from a URL."""
    if not image_url: return None
    logger.info(f"Downloading image from {image_url}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'} # Basic user agent
        # Use verify_tls from config
        r_download = requests.get(image_url, headers=headers, verify=config.verify_tls, stream=False, timeout=45)
        r_download.raise_for_status()
        img_bytes: bytes = r_download.content
        content_type: str = r_download.headers.get("Content-Type", "application/octet-stream")
        # Basic validation
        if not img_bytes or content_type.startswith("text/html"):
            logger.warning(f"Invalid image data or HTML page received from {image_url}")
            return None
        if not content_type.startswith('image/'):
            logger.warning(f"Content type '{content_type}' from {image_url} might not be an image.")
        logger.info(f"Image downloaded ({len(img_bytes)} bytes, type: {content_type}).")
        return {"data": img_bytes, "content_type": content_type, "size": len(img_bytes)}
    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading image: {image_url}")
        return None
    except requests.exceptions.MissingSchema:
        logger.error(f"Invalid URL (Missing Schema) for image download: '{image_url}'")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download image from {image_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading image {image_url}: {e}", exc_info=True)
        return None

# --- Matrix Image Upload Helper (Async - from Old Code) ---
async def upload_image_to_matrix(matrix_client: AsyncClient, image_url: str, config: config_module.MyConfig) -> str:
    """Downloads an image and uploads it to Matrix, returning the MXC URI."""
    if not image_url: return ""
    if not matrix_client or not matrix_client.access_token:
        logger.error("Matrix client not ready or not logged in for image upload.")
        return ""

    # Run synchronous download in a separate thread
    download_result = await asyncio.to_thread(_sync_download_image, image_url, config)
    if not download_result:
        logger.warning(f"Failed to download image {image_url} for Matrix upload.")
        return ""

    img_bytes = download_result["data"]
    content_type = download_result["content_type"]
    filesize = download_result["size"]

    logger.info(f"Uploading image ({filesize} bytes, type: {content_type}) from {image_url} to Matrix...")
    img_data_stream = io.BytesIO(img_bytes)
    try:
        # Try to get a reasonable filename
        filename = os.path.basename(urljoin(image_url, '.')) or "image.dat" # Basic filename extraction
        if '?' in filename: filename = filename.split('?', 1)[0] # Remove query params

        resp, maybe_keys = await matrix_client.upload(
            img_data_stream,
            content_type=content_type,
            filename=filename,
            filesize=filesize
        )
        if isinstance(resp, UploadResponse) and resp.content_uri:
            logger.info(f"Image uploaded successfully: {resp.content_uri}")
            return resp.content_uri
        else:
            logger.error(f"Matrix upload failed. Response: {resp}")
            return ""
    except Exception as e:
        logger.error(f"Exception during Matrix image upload: {e}", exc_info=True)
        return ""
    finally:
        img_data_stream.close()

# --- Formatted Message Sender (from Old Code - Used by Help) ---
async def send_formatted_message(bot: botlib.Bot, room_id: str, plain_body: str, html_body: str):
    """Sends a message with plain text body and HTML formatted body."""
    try:
        content = {
            "msgtype": "m.notice", # Use notice for bot messages
            "format": "org.matrix.custom.html",
            "body": plain_body, # Plain text fallback
            "formatted_body": html_body # HTML version
        }
        # Use the underlying client's room_send for raw content
        response = await bot.api.async_client.room_send(
            room_id=room_id,
            message_type="m.room.message", # Standard message type
            content=content
        )
        # Check if the response indicates an error (specific to nio's potential return types)
        if isinstance(response, RoomSendError):
            logger.error(f"Failed to send formatted message to {room_id}: {response.message} (Status Code: {response.status_code})")
        # Add other potential error checks if needed based on nio documentation/behavior
    except Exception as e:
        logger.error(f"Exception sending formatted message to {room_id}: {e}", exc_info=True)


# --- Slugify Function (from Your Code) ---
def slugify(text):
    """
    Convert a string into a URL-friendly 'slug'.
    Lowercase, remove non-word characters (alphanumeric & underscore),
    replace whitespace with hyphens, and strip leading/trailing hyphens.
    """
    if not text: return ""
    text = str(text).lower() # Ensure input is string
    text = re.sub(r'[^\w\s-]', '', text) # Remove unwanted chars
    text = re.sub(r'\s+', '-', text)     # Replace whitespace with hyphens
    text = re.sub(r'-{2,}', '-', text)   # Replace multiple hyphens
    text = text.strip('-')             # Strip leading/trailing hyphens
    return text

# --- Nested Get Helper (from Your Code) ---
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

# --- Media Info Card Sender (Updated to use MXC URI) ---
async def send_media_info_card(bot, room_id: str, media_data: dict, is_added: bool, config, media_type: str):
    """Sends a formatted card notification to Matrix, uploading poster to get MXC URI."""

    if not media_data:
        logger.error("send_media_info_card called with empty media_data.")
        return

    event_type = get_nested(media_data, 'event_type', default='Info') # Default to 'Info' if not from webhook

    # --- Determine Title, Year/Season/Episode, Overview ---
    title = "Unknown Title"
    year_or_episode = ""
    overview = get_nested(media_data, 'overview', default="No overview available.")
    tmdb_id = None
    tvdb_id = None
    imdb_id = None
    series_title_for_log = ""

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
        episode_title = get_nested(media_data, 'title', default="Unknown Episode") # Episode title is top-level
        season_num = get_nested(media_data, 'seasonNumber')
        episode_num = get_nested(media_data, 'episodeNumber')
        title = f"{series_title} - {episode_title}" # Combined display title
        if season_num is not None and episode_num is not None:
            year_or_episode = f" (S{season_num:02d}E{episode_num:02d})"
        # IDs from nested series data
        tvdb_id = get_nested(series_data, 'tvdbId')
        tmdb_id = get_nested(series_data, 'tvdbId') # Assuming same as TVDB ID for series TMDB link
        imdb_id = get_nested(series_data, 'imdbId')
        logger.info(f"Constructing Sonarr info card for '{series_title} S{season_num:02d}E{episode_num:02d}'")

    elif media_type == 'series': # Handle case for 'sonarr info' command
        title = get_nested(media_data, 'title', default=title)
        series_title_for_log = title
        year = get_nested(media_data, 'year')
        if year: year_or_episode = f" ({year})"
        tvdb_id = get_nested(media_data, 'tvdbId')
        tmdb_id = get_nested(media_data, 'tvdbId') # Assuming same as TVDB ID for series TMDB link
        imdb_id = get_nested(media_data, 'imdbId')
        logger.info(f"Constructing Sonarr info card for Series: '{title}'")

    else:
        logger.error(f"Unsupported media_type '{media_type}' in send_media_info_card.")
        return

    # --- Determine Poster URL (from *Arr data) ---
    poster_url_http = None # The original http(s) url
    images = []
    base_url_for_relative_path = None

    if media_type == 'movie':
        images = get_nested(media_data, 'images', default=[])
        base_url_for_relative_path = config.radarr_url
    elif media_type == 'episode':
        series_data_for_poster = get_nested(media_data, 'series', default={})
        images = get_nested(series_data_for_poster, 'images', default=[])
        base_url_for_relative_path = config.sonarr_url
    elif media_type == 'series': # For 'sonarr info'
        images = get_nested(media_data, 'images', default=[]) # Images are top-level for series details/lookup
        base_url_for_relative_path = config.sonarr_url

    for image in images:
        if isinstance(image, dict) and image.get('coverType') == 'poster':
            poster_url_http = image.get('remoteUrl') or image.get('url')
            if poster_url_http:
                if poster_url_http.startswith('/') and base_url_for_relative_path:
                    if not base_url_for_relative_path.startswith(('http://', 'https://')):
                         base_url_for_relative_path = 'http://' + base_url_for_relative_path
                    cleaned_base_url = base_url_for_relative_path.rstrip('/')
                    poster_url_http = cleaned_base_url + poster_url_http
                    logger.debug(f"Prepended base URL to relative poster URL: {poster_url_http}")
                elif poster_url_http.startswith('/') and not base_url_for_relative_path:
                     logger.warning(f"Poster URL '{poster_url_http}' looks relative, but base URL for {media_type} is not configured.")
                     poster_url_http = None # Cannot use relative URL
                if poster_url_http: logger.info(f"Found poster URL: {poster_url_http}"); break # Use the first one found
    if not poster_url_http: logger.info("No poster URL found in media data.")

    # --- *** FIX: Upload Poster and get MXC URI *** ---
    mxc_uri = ""
    if poster_url_http:
        # Pass the underlying nio client (bot.api.async_client) to the upload helper
        mxc_uri = await upload_image_to_matrix(bot.api.async_client, poster_url_http, config)
        if not mxc_uri:
             logger.warning(f"Failed to upload poster {poster_url_http} to Matrix. Card will not have image.")
    # --- *** END FIX *** ---

    # --- Construct Links ---
    links_html = ""
    if (tvdb_id and (media_type == 'episode' or media_type == 'series')): links_html += f' <a href="https://thetvdb.com/?tab=series&id={tvdb_id}">TVDB</a>'
    if imdb_id: links_html += f' <a href="https://www.imdb.com/title/{imdb_id}/">IMDb</a>'

    arr_base_url = config.sonarr_url if (media_type == 'episode' or media_type == 'series') else config.radarr_url
    arr_link = None; arr_name = "Sonarr" if (media_type == 'episode' or media_type == 'series') else "Radarr"
    if arr_base_url:
        if not arr_base_url.startswith(('http://', 'https://')): arr_base_url = 'http://' + arr_base_url
        cleaned_base_url = arr_base_url.rstrip('/') + '/'
        if media_type == 'episode':
            series_title_for_slug = get_nested(media_data, 'series', 'title')
            series_id_fallback = get_nested(media_data, 'series', 'id')
            if series_title_for_slug: series_slug = slugify(series_title_for_slug)
            else: series_slug = None
            if series_slug: arr_link = urljoin(cleaned_base_url, f'series/{series_slug}')
            elif series_id_fallback: arr_link = urljoin(cleaned_base_url, f'series/{series_id_fallback}'); logger.warning("Using Sonarr ID link fallback (episode).")
        elif media_type == 'series':
            series_title_for_slug = get_nested(media_data, 'title') # Title is top-level for series info
            series_id_fallback = get_nested(media_data, 'id') # ID is top-level for series info
            if series_title_for_slug: series_slug = slugify(series_title_for_slug)
            else: series_slug = None
            if series_slug: arr_link = urljoin(cleaned_base_url, f'series/{series_slug}')
            elif series_id_fallback: arr_link = urljoin(cleaned_base_url, f'series/{series_id_fallback}'); logger.warning("Using Sonarr ID link fallback (series).")
        else: # Radarr (movie)
            movie_id = get_nested(media_data, 'id')
            if movie_id: arr_link = urljoin(cleaned_base_url, f'movie/{movie_id}')
    if arr_link: links_html += f' <a href="{arr_link}">{arr_name}</a>'

    # --- Construct Message Body ---
    status_emoji = "✅" # Default emoji
    # Determine status text based on context (download vs. info command)
    if event_type == 'Download': status_text = "Downloaded"
    elif event_type == 'Grab': status_text = "Grabbed"
    elif is_added: status_text = "Info (Added)" # For info command on added item
    else: status_text = "Info (Not Added)"     # For info command on unadded item

    text_body = f"{status_emoji} {status_text}: {title}{year_or_episode}"
    release_title = get_nested(media_data, 'releaseTitle') # Include release if passed (e.g., from webhook)
    if release_title: text_body += f" - Release: {release_title}"

    html_body = f"""<p>{status_emoji} <strong>{status_text}: {title}{year_or_episode}</strong></p>"""
    if release_title: html_body += f"<p><em>Release:</em> {release_title}</p>"

    # --- *** FIX: Use mxc_uri in img tag *** ---
    if mxc_uri:
        # Add width/height/style attributes as needed for your client
        html_body += f'<p><img src="{mxc_uri}" alt="Poster Image" width="100" /></p>'
    # --- *** END FIX *** ---

    if overview: html_body += f"<p>{overview}</p>"
    else: html_body += "<p>No overview available.</p>"
    if links_html: html_body += f"<p>Links:{links_html}</p>"

    # --- Send Message using send_formatted_message ---
    # This reuses the function needed by help.py
    await send_formatted_message(bot, room_id, text_body, html_body)
