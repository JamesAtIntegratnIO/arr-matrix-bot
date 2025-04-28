import logging
import asyncio
import requests
import io
import os
import html
import simplematrixbotlib as botlib # Import botlib
from typing import Optional, Dict, Any, List
from nio import AsyncClient, UploadResponse, RoomSendResponse, RoomSendError # Ensure RoomSendError is imported
from urllib.parse import urljoin
from . import tvdb as tvdb_utils
from .. import config as config_module

logger = logging.getLogger(__name__)

# --- Byte Formatting Helper ---
# ... (remains the same)
def _format_bytes(size_bytes: int) -> str:
    if not isinstance(size_bytes, (int, float)) or size_bytes < 0: return "N/A"
    if size_bytes < 1024: return f"{size_bytes} B"
    elif size_bytes < 1024**2: return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024**3: return f"{size_bytes/1024**2:.2f} MB"
    elif size_bytes < 1024**4: return f"{size_bytes/1024**3:.2f} GB"
    else: return f"{size_bytes/1024**4:.2f} TB"

# --- Image Download Helper ---
# ... (remains the same)
def _sync_download_image(image_url: str, config: config_module.MyConfig) -> Optional[Dict[str, Any]]:
    if not image_url: return None
    logger.info(f"Downloading image from {image_url}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r_download = requests.get(image_url, headers=headers, verify=config.verify_tls, stream=False, timeout=45); r_download.raise_for_status()
        img_bytes: bytes = r_download.content; content_type: str = r_download.headers.get("Content-Type", "application/octet-stream")
        if not img_bytes or content_type.startswith("text/html"): logger.warning(f"Invalid image data from {image_url}"); return None
        if not content_type.startswith('image/'): logger.warning(f"Content type '{content_type}' might not be image.")
        logger.info(f"Image downloaded ({len(img_bytes)} bytes, type: {content_type}).")
        return {"data": img_bytes, "content_type": content_type, "size": len(img_bytes)}
    except requests.exceptions.Timeout: logger.error(f"Timeout downloading: {image_url}"); return None
    except requests.exceptions.MissingSchema: logger.error(f"Invalid URL (Missing Schema): '{image_url}'"); return None
    except requests.exceptions.RequestException as e: logger.error(f"Failed to download image: {e}"); return None

# --- Matrix Image Upload Helper ---
# ... (remains the same)
async def upload_image_to_matrix(matrix_client: AsyncClient, image_url: str, config: config_module.MyConfig) -> str:
    if not image_url: return ""
    if not matrix_client or not matrix_client.access_token: logger.error("Matrix client not ready for upload."); return ""
    download_result = await asyncio.to_thread(_sync_download_image, image_url, config)
    if not download_result: return ""
    img_bytes = download_result["data"]; content_type = download_result["content_type"]; filesize = download_result["size"]
    logger.info(f"Uploading image ({filesize} bytes, type: {content_type}) to Matrix...")
    img_data_stream = io.BytesIO(img_bytes)
    try:
        filename = os.path.basename(image_url.split('?')[0]) or "poster.jpg"
        resp, maybe_keys = await matrix_client.upload(img_data_stream, content_type=content_type, filename=filename, filesize=filesize)
        if isinstance(resp, UploadResponse) and resp.content_uri: logger.info(f"Image uploaded: {resp.content_uri}"); return resp.content_uri
        else: logger.error(f"Matrix upload failed. Response: {resp}"); return ""
    except Exception as e: logger.exception(f"Failed to upload image: {e}"); return ""
    finally: img_data_stream.close()

# --- NEW: Formatted Message Sender ---
async def send_formatted_message(bot: botlib.Bot, room_id: str, plain_body: str, html_body: str):
    """Sends a message with plain text body and HTML formatted body."""
    try:
        content = {
            "msgtype": "m.text",
            "format": "org.matrix.custom.html",
            "body": plain_body,
            "formatted_body": html_body
        }
        response = await bot.api.async_client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content
        )
        if isinstance(response, RoomSendError):
            logger.error(f"Failed to send formatted message to {room_id}: {response.message}")
    except Exception as e:
        logger.error(f"Exception sending formatted message to {room_id}: {e}")


# --- Generic Media Info Card Sender ---
# ... (remains the same, uses upload_image_to_matrix and _format_bytes internally)
async def send_media_info_card(
    bot: botlib.Bot,
    room_id: str,
    media_data: Dict[str, Any],
    is_added: bool,
    config: config_module.MyConfig,
    media_type: str # 'series' or 'movie'
):
    service_name = "Sonarr" if media_type == 'series' else "Radarr"
    logger.info(f"Constructing {service_name} info card for '{media_data.get('title', 'N/A')}'")
    title = media_data.get('title', 'Unknown Title'); year = media_data.get('year'); overview = media_data.get('overview', '')
    identifier_value = None; identifier_name = ""; status = None; monitored = None; path = None; size_on_disk = 0
    seasons_info = ""; episodes_info = ""; downloaded_info = ""; quality_profile_info = ""; imdb_rating_str = ""; tmdb_rating_str = ""

    if media_type == 'series':
        identifier_value = media_data.get('tvdbId'); identifier_name = "TVDb"
        if is_added:
            status = media_data.get('status', 'N/A'); monitored = media_data.get('monitored', False); path = media_data.get('path')
            stats = media_data.get('statistics', {}); size_on_disk = stats.get('sizeOnDisk', 0); episode_count = stats.get('episodeCount', 0)
            episode_file_count = stats.get('episodeFileCount', 0); percent_of_episodes = stats.get('percentOfEpisodes', 0)
            seasons_list = media_data.get('seasons', []); season_count = len(seasons_list) if seasons_list else stats.get('seasonCount', 0)
            seasons_info = f"<b>Seasons:</b> {season_count}"; episodes_info = f"<b>Episodes:</b> {episode_file_count}/{episode_count} ({percent_of_episodes:.1f}%)"
        ratings = media_data.get('ratings', {}); rating_value = ratings.get('value', 0); rating_votes = ratings.get('votes', 0)
        if rating_value > 0: tmdb_rating_str = f"TVDb: {rating_value:.1f}/10 ({rating_votes} votes)"
    elif media_type == 'movie':
        identifier_value = media_data.get('tmdbId'); identifier_name = "TMDb"
        if is_added:
            status = media_data.get('status', 'N/A'); monitored = media_data.get('monitored', False); path = media_data.get('path')
            size_on_disk = media_data.get('sizeOnDisk', 0); has_file = media_data.get('hasFile', False); quality_profile_id = media_data.get('qualityProfileId')
            downloaded_info = f"<b>Downloaded:</b> {'Yes' if has_file else 'No'}"
            if quality_profile_id: quality_profile_info = f"<b>Quality Profile ID:</b> {quality_profile_id}"
        ratings = media_data.get('ratings', {})
        imdb_rating = ratings.get('imdb', {}).get('value', 0); imdb_votes = ratings.get('imdb', {}).get('votes', 0)
        tmdb_rating = ratings.get('tmdb', {}).get('value', 0); tmdb_votes = ratings.get('tmdb', {}).get('votes', 0)
        if imdb_rating > 0: imdb_rating_str = f"IMDb: {imdb_rating:.1f}/10 ({imdb_votes} votes)"
        if tmdb_rating > 0: tmdb_rating_str = f"TMDb: {tmdb_rating:.1f}/10 ({tmdb_votes} votes)"

    mxc_uri = ""; poster_url_to_upload = ""
    if media_type == 'series' and identifier_value and config.tvdb_api_key:
        tvdb_poster_url = await tvdb_utils.get_tvdb_poster_url(media_type, str(identifier_value), config)
        if tvdb_poster_url: poster_url_to_upload = tvdb_poster_url; logger.info(f"Using TVDB poster URL: {poster_url_to_upload}")
        else: logger.info(f"No poster URL from TVDB. Checking {service_name} images...")
    if not poster_url_to_upload:
        images = media_data.get('images', []); relative_url = None; base_url_config = None
        if media_type == 'series': base_url_config = config.sonarr_url
        elif media_type == 'movie': base_url_config = config.radarr_url
        for img in images:
            if img.get('coverType') == 'poster':
                if img.get('remoteUrl') and img['remoteUrl'].startswith(('http://', 'https://')): relative_url = img['remoteUrl']; break
                elif img.get('url'): relative_url = img['url']; break
        if relative_url:
            if relative_url.startswith('/'):
                if base_url_config: base_url_abs = base_url_config.rstrip('/') + '/'; poster_url_to_upload = urljoin(base_url_abs, relative_url.lstrip('/')); logger.info(f"Using {service_name} fallback (constructed): {poster_url_to_upload}")
                else: logger.warning(f"Cannot construct {service_name} URL: base URL missing.")
            elif relative_url.startswith(('http://', 'https://')): poster_url_to_upload = relative_url; logger.info(f"Using {service_name} fallback (absolute): {poster_url_to_upload}")
            else: logger.warning(f"{service_name} image URL unexpected format: {relative_url}")
    if poster_url_to_upload: mxc_uri = await upload_image_to_matrix(bot.api.async_client, poster_url_to_upload, config)
    else: logger.info(f"No poster URL found.")

    esc_title = html.escape(title); esc_year = f"({html.escape(str(year))})" if year else ""; esc_overview = html.escape(overview[:400]) + ("..." if len(overview) > 400 else "")
    esc_status = html.escape(status.capitalize()) if status else None; esc_path = html.escape(path) if path else None
    html_details: List[str] = []; text_details: List[str] = []
    html_header = f'<h3 style="margin-top: 0; margin-bottom: 4px;">{esc_title} {esc_year}</h3>'
    text_header = f"{title} {f'({year})' if year else ''}".strip() + f" [{identifier_name}: {identifier_value or 'N/A'}]"
    added_status_text = f"(Already in {service_name})" if is_added else f"(Not in {service_name})"
    html_details.append(f'<p style="margin: 0 0 8px 0; font-size: .9em; font-style: italic;">{added_status_text}</p>')
    text_details.append(added_status_text)
    if esc_overview: html_details.append(f'<p style="margin: 0 0 4px 0; font-size: .9em;">{esc_overview}</p>'); text_details.append(overview)
    if is_added:
        parts_h = []; parts_t = []
        if esc_status: parts_h.append(f"<b>Status:</b> {esc_status}"); parts_t.append(f"Status: {status.capitalize()}")
        if monitored is not None: parts_h.append(f"<b>Monitored:</b> {'Yes' if monitored else 'No'}"); parts_t.append(f"Monitored: {'Yes' if monitored else 'No'}")
        if media_type == 'series':
             if seasons_info: parts_h.append(seasons_info); parts_t.append(seasons_info.replace('<b>','').replace('</b>',''))
             if episodes_info: parts_h.append(episodes_info); parts_t.append(episodes_info.replace('<b>','').replace('</b>',''))
        elif media_type == 'movie':
             if downloaded_info: parts_h.append(downloaded_info); parts_t.append(downloaded_info.replace('<b>','').replace('</b>',''))
             if quality_profile_info: parts_h.append(quality_profile_info); parts_t.append(quality_profile_info.replace('<b>','').replace('</b>',''))
        if size_on_disk > 0: parts_h.append(f"<b>Size:</b> {_format_bytes(size_on_disk)}"); parts_t.append(f"Size: {_format_bytes(size_on_disk)}")
        if esc_path: parts_h.append(f"<b>Path:</b> <code>{esc_path}</code>"); parts_t.append(f"Path: {path}")
        if parts_h: html_details.append('<p style="margin: 4px 0 0 0; font-size: .9em;">' + "<br>".join(parts_h) + '</p>'); text_details.append("\n".join(parts_t))
    rating_parts_h = []; rating_parts_t = []
    if imdb_rating_str: rating_parts_h.append(imdb_rating_str); rating_parts_t.append(imdb_rating_str)
    if tmdb_rating_str: rating_parts_h.append(tmdb_rating_str); rating_parts_t.append(tmdb_rating_str)
    if rating_parts_h:
        html_details.append(f'<p style="margin: 4px 0 0 0; font-size: .8em; color: #888;">Ratings: {" | ".join(rating_parts_h)}</p>')
        text_details.append(f"Ratings: {' | '.join(rating_parts_t)}")

    img_tag = f'<img src="{mxc_uri}" style="max-width:100px; height:auto; border-radius:4px; margin-right:12px; vertical-align:top; object-fit: cover;" alt="Poster"/>' if mxc_uri else ""
    html_body_content = html_header + "\n".join(html_details)
    html_body = f"""<table style="border: none; width: 100%; border-spacing: 0;"><tbody><tr><td style="width: 1px; padding: 0; vertical-align: top;">{img_tag}</td><td style="padding: 0 0 0 12px; vertical-align: top;">{html_body_content}</td></tr></tbody></table>""".strip().replace('\n', '')
    text_body = text_header;
    if text_details: text_body += "\n" + "\n".join(text_details)
    # Use the other util function to send the card content
    await send_formatted_message(bot, room_id, text_body, html_body)
    # Return True/False based on whether send_formatted_message succeeded?
    # For now, assume it logs errors internally and return True for flow control.
    return True
