import logging
import asyncio
import requests
import json
from typing import Optional, Dict
from .. import config as config_module

logger = logging.getLogger(__name__)

# --- Simple In-Memory Cache for TVDB Token ---
_tvdb_token_cache: Optional[str] = None
_tvdb_token_lock = asyncio.Lock() # Prevent race conditions during token fetch

# --- TVDB Token Management ---
def _sync_get_tvdb_token(config: config_module.MyConfig) -> Optional[str]:
    """Synchronous part of fetching TVDB token. Runs in a thread."""
    if not config.tvdb_api_key or not config.tvdb_base_url:
         logger.error("TVDB configuration (api_key or base_url) not loaded.")
         return None
    logger.info("Requesting TVDB API token...")
    url = f"{config.tvdb_base_url.rstrip('/')}/login"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {"apikey": config.tvdb_api_key}
    try:
        response = requests.post(url, json=payload, headers=headers, verify=config.verify_tls, timeout=15)
        response.raise_for_status()
        token = response.json().get("data", {}).get("token")
        if not token:
             logger.error("TVDB token not found in API response data.")
             return None
        logger.info("TVDB token obtained successfully.")
        return token
    except requests.exceptions.Timeout: logger.error(f"Timeout requesting TVDB token from {url}"); return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get TVDB token: {e}")
        if hasattr(e, 'response') and e.response is not None: logger.error(f"Response Status: {e.response.status_code}, Body: {e.response.text[:500]}...")
        return None
    except (KeyError, ValueError, json.JSONDecodeError) as e: logger.error(f"Failed to parse TVDB token response: {e}"); return None

async def _fetch_and_cache_tvdb_token(config: config_module.MyConfig) -> Optional[str]:
    """Fetches TVDB token async and updates cache."""
    global _tvdb_token_cache
    token = await asyncio.to_thread(_sync_get_tvdb_token, config)
    _tvdb_token_cache = token # Cache even if None on failure
    return token

async def ensure_tvdb_token(config: config_module.MyConfig) -> Optional[str]:
    """Gets cached TVDB token or fetches a new one if needed."""
    global _tvdb_token_cache
    if _tvdb_token_cache: return _tvdb_token_cache
    async with _tvdb_token_lock:
        if _tvdb_token_cache: return _tvdb_token_cache
        return await _fetch_and_cache_tvdb_token(config)

# --- Get TVDB Poster URL ---
def _sync_get_poster_url(media_type: str, thetvdb_id: str, token: str, config: config_module.MyConfig) -> str:
    """Synchronous part of getting TVDB poster URL. Runs in a thread."""
    if not config.tvdb_base_url: logger.error("TVDB Base URL missing."); return ""
    if not thetvdb_id or not token: logger.error("TVDB ID or token missing."); return ""
    logger.info(f"Fetching TVDB poster URL for {media_type} ID {thetvdb_id}...")
    # TVDB uses 'series' for episodes, movies for movies
    lookup_type = 'series' if media_type in ['series', 'episode', 'standard', 'anime', 'daily'] else media_type
    endpoint_map: Dict[str, str] = {"movie": "movies", "series": "series"}
    path_component = endpoint_map.get(lookup_type)
    if not path_component: logger.error(f"Invalid media_type for TVDB lookup: '{media_type}'"); return ""

    url = f"{config.tvdb_base_url.rstrip('/')}/{path_component}/{thetvdb_id}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, verify=config.verify_tls, timeout=20); response.raise_for_status()
        data = response.json().get("data")
        if isinstance(data, dict):
            image_url = data.get("image", "")
            if image_url: logger.info(f"Found TVDB poster URL: {image_url}"); return image_url
            else: logger.info(f"No poster image URL in TVDB data for {lookup_type} ID {thetvdb_id}."); return ""
        else: logger.warning(f"TVDB response has no 'data' dict: {url}"); return ""
    except requests.exceptions.Timeout: logger.error(f"Timeout fetching TVDB metadata: {url}"); return ""
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching TVDB metadata: {e}")
        if e.response is not None: logger.error(f"Status: {e.response.status_code}, Body: {e.response.text[:500]}...")
        if e.response is not None and e.response.status_code == 401:
             logger.warning("TVDB request unauthorized (401). Invalidating token cache.")
             global _tvdb_token_cache; _tvdb_token_cache = None
        return ""
    except requests.exceptions.RequestException as e: logger.error(f"Failed to get TVDB metadata: {e}"); return ""
    except (KeyError, ValueError, json.JSONDecodeError) as e: logger.error(f"Failed to parse TVDB metadata: {e}"); return ""

async def get_tvdb_poster_url(media_type: str, thetvdb_id: str, config: config_module.MyConfig) -> str:
    """
    Async wrapper for getting TVDB poster URL, ensuring token is available.
    media_type should be 'series' or 'movie'.
    """
    if not config.tvdb_api_key: logger.info("Skip TVDB: API key missing."); return ""
    if not thetvdb_id: logger.info("Skip TVDB: ID missing."); return ""
    token = await ensure_tvdb_token(config)
    if not token: logger.error("Cannot get TVDB poster: token unavailable."); return ""
    # Pass the simplified media type ('series' or 'movie')
    lookup_media_type = 'series' if media_type in ['series', 'episode', 'standard', 'anime', 'daily'] else 'movie'
    return await asyncio.to_thread(_sync_get_poster_url, lookup_media_type, str(thetvdb_id), token, config)