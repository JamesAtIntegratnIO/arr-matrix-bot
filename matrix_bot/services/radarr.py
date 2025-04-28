import asyncio # Added
import aiohttp  # Added
import logging
import ssl      # Added for verify_tls handling
from urllib.parse import urljoin
from typing import Optional, List, Dict, Any # Ensure these are imported

logger = logging.getLogger(__name__)

# Default timeout in seconds - can be adjusted
REQUEST_TIMEOUT = 15

# --- Helper for TLS verification (Copied from sonarr.py) ---
def _get_ssl_context(verify_tls: bool):
    if verify_tls:
        return None # Use default SSL context which verifies
    else:
        # Create a context that does NOT verify certificates
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        logger.warning("TLS verification is DISABLED for Radarr requests.")
        return context

# --- *** ADD PING FUNCTION (mirrors sonarr's test_sonarr_connection) *** ---
async def ping_radarr(radarr_url: str, api_key: str, verify_tls: bool = True) -> bool:
    """(Async) Tests the connection and authentication to the Radarr API using /system/status."""
    if not radarr_url or not api_key:
        logger.error("Cannot test Radarr connection: URL or API Key is missing.")
        return False

    if not radarr_url.startswith(('http://', 'https://')):
         logger.warning(f"Radarr URL '{radarr_url}' is missing scheme, defaulting to http://")
         radarr_url = 'http://' + radarr_url

    api_endpoint = urljoin(radarr_url, '/api/v3/system/status') # Radarr also uses v3
    headers = {'X-Api-Key': api_key}
    ssl_context = _get_ssl_context(verify_tls)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session: # Shorter timeout for test
            logger.info(f"Testing async Radarr connection to {api_endpoint}...")
            async with session.get(api_endpoint, headers=headers, ssl=ssl_context) as response:
                response.raise_for_status()
                # Optionally check response content if needed, e.g., version
                status_data = await response.json()
                if isinstance(status_data, dict) and 'version' in status_data:
                     logger.info(f"Radarr connection test successful ({api_endpoint}, Version: {status_data.get('version', 'N/A')}).")
                     return True
                else:
                     logger.warning(f"Radarr connection test to {api_endpoint} successful, but response format unexpected: {status_data}")
                     return True # Still counts as success if status was 2xx

    except asyncio.TimeoutError:
        logger.error(f"Radarr connection test failed: Timeout connecting to {api_endpoint}")
        return False
    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            logger.error(f"Radarr connection test failed: Authentication error (Invalid API Key?). Status: 401 ({api_endpoint})")
        else:
            logger.error(f"Radarr connection test failed: HTTP error {e.status} connecting to {api_endpoint}")
        return False
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Radarr connection test failed ({api_endpoint}): Connection error - {e}")
        return False
    except Exception as e:
         logger.error(f"An unexpected error occurred during Radarr connection test ({api_endpoint}): {e}", exc_info=True)
         return False
# --- *** END PING FUNCTION *** ---


# --- Existing Radarr Service Functions ---

async def search_radarr_movie(search_term: str, radarr_url: str, api_key: str, verify_tls: bool = True) -> Optional[List[Dict[str, Any]]]:
    """(Async) Searches Radarr's movie lookup endpoint."""
    if not radarr_url or not api_key:
        logger.error("Radarr URL or API Key is not configured.")
        return None

    if not radarr_url.startswith(('http://', 'https://')):
         radarr_url = 'http://' + radarr_url

    api_endpoint = urljoin(radarr_url, '/api/v3/movie/lookup')
    headers = {'X-Api-Key': api_key}
    params = {'term': search_term}
    ssl_context = _get_ssl_context(verify_tls)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
            logger.info(f"Sending async request to Radarr lookup: {api_endpoint} with term: '{search_term}'")
            async with session.get(api_endpoint, headers=headers, params=params, ssl=ssl_context) as response:
                response.raise_for_status()
                try:
                    results = await response.json()
                    if isinstance(results, list):
                        logger.info(f"Radarr lookup successful. Found {len(results)} potential matches for '{search_term}'.")
                        return results
                    else:
                        logger.error(f"Radarr API ({api_endpoint}) returned unexpected data type: {type(results)}. Expected list.")
                        return None
                except aiohttp.ContentTypeError:
                    body_preview = await response.text()
                    logger.error(f"Failed to decode JSON response from Radarr ({api_endpoint}). Status: {response.status}, Body: {body_preview[:200]}...")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Error communicating with Radarr API ({api_endpoint}): Request timed out after {REQUEST_TIMEOUT} seconds.")
        return None
    except aiohttp.ClientResponseError as e:
        logger.error(f"Error communicating with Radarr API ({api_endpoint}): HTTP {e.status} - {e.message}")
        try: body_preview = await e.response.text(); logger.error(f"Radarr API Response Body (partial): {body_preview[:200]}...")
        except Exception: pass
        return None
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Error communicating with Radarr API ({api_endpoint}): Connection error - {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Radarr search ({api_endpoint}): {e}", exc_info=True)
        return None


async def lookup_radarr_movie_by_tmdb(tmdb_id: int, radarr_url: str, api_key: str, verify_tls: bool = True) -> Optional[List[Dict[str, Any]]]:
     """(Async) Looks up a Radarr movie by TMDb ID."""
     if not radarr_url or not api_key: logger.error("Radarr URL or API Key is not configured."); return None
     if not tmdb_id or tmdb_id <= 0: logger.error("Invalid TMDb ID provided for lookup."); return None

     if not radarr_url.startswith(('http://', 'https://')): radarr_url = 'http://' + radarr_url

     api_endpoint = urljoin(radarr_url, '/api/v3/movie/lookup')
     headers = {'X-Api-Key': api_key}
     params = {'term': f"tmdb:{tmdb_id}"} # Use term parameter for TMDb lookup
     ssl_context = _get_ssl_context(verify_tls)

     try:
         async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
             logger.info(f"Sending async request to Radarr TMDb lookup: {api_endpoint} for TMDb ID: {tmdb_id}")
             async with session.get(api_endpoint, headers=headers, params=params, ssl=ssl_context) as response:
                 response.raise_for_status()
                 try:
                     results = await response.json()
                     if isinstance(results, list):
                         logger.info(f"Radarr TMDb lookup successful. Found {len(results)} matches for TMDb ID {tmdb_id}.")
                         # Radarr lookup might return multiple results even for ID lookup? Filter if needed.
                         # For now, return the whole list.
                         return results
                     else:
                         logger.error(f"Radarr TMDb lookup API ({api_endpoint}) returned unexpected data type: {type(results)}. Expected list.")
                         return None
                 except aiohttp.ContentTypeError:
                     body_preview = await response.text()
                     logger.error(f"Failed to decode JSON response from Radarr TMDb lookup API ({api_endpoint}). Status: {response.status}, Body: {body_preview[:200]}...")
                     return None
     except asyncio.TimeoutError:
         logger.error(f"Error looking up Radarr movie by TMDb ID {tmdb_id} ({api_endpoint}): Request timed out.")
         return None
     except aiohttp.ClientResponseError as e:
         logger.error(f"Error looking up Radarr movie by TMDb ID {tmdb_id} ({api_endpoint}): HTTP {e.status} - {e.message}")
         try: body_preview = await e.response.text(); logger.error(f"Radarr TMDb Lookup API Response Body (partial): {body_preview[:200]}...")
         except Exception: pass
         return None
     except aiohttp.ClientConnectionError as e:
         logger.error(f"Error looking up Radarr movie by TMDb ID {tmdb_id} ({api_endpoint}): Connection error - {e}")
         return None
     except Exception as e:
         logger.error(f"An unexpected error occurred fetching Radarr movie by TMDb ID ({api_endpoint}): {e}", exc_info=True)
         return None


async def get_radarr_movie_details(movie_id: int, radarr_url: str, api_key: str, verify_tls: bool = True) -> Optional[Dict[str, Any]]:
    """(Async) Gets details for a specific movie from Radarr."""
    if not radarr_url or not api_key: logger.error("Radarr URL or API Key is not configured."); return None
    if not movie_id or movie_id <= 0: logger.error("Invalid movie_id provided for details lookup."); return None

    if not radarr_url.startswith(('http://', 'https://')): radarr_url = 'http://' + radarr_url

    api_endpoint = urljoin(radarr_url, f'/api/v3/movie/{movie_id}')
    headers = {'X-Api-Key': api_key}
    ssl_context = _get_ssl_context(verify_tls)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
            logger.info(f"Requesting async details for Radarr movie ID: {movie_id} from {api_endpoint}")
            async with session.get(api_endpoint, headers=headers, ssl=ssl_context) as response:
                response.raise_for_status()
                try:
                    details = await response.json()
                    if isinstance(details, dict):
                        logger.info(f"Successfully retrieved details for Radarr movie ID: {movie_id}")
                        return details
                    else:
                        logger.error(f"Radarr details API ({api_endpoint}) returned unexpected data type: {type(details)}. Expected dict.")
                        return None
                except aiohttp.ContentTypeError:
                    body_preview = await response.text()
                    logger.error(f"Failed to decode JSON response from Radarr details API ({api_endpoint}). Status: {response.status}, Body: {body_preview[:200]}...")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Error getting details for Radarr movie ID {movie_id} ({api_endpoint}): Request timed out.")
        return None
    except aiohttp.ClientResponseError as e:
        logger.error(f"Error getting details for Radarr movie ID {movie_id} ({api_endpoint}): HTTP {e.status} - {e.message}")
        try: body_preview = await e.response.text(); logger.error(f"Radarr Details API Response Body (partial): {body_preview[:200]}...")
        except Exception: pass
        return None
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Error getting details for Radarr movie ID {movie_id} ({api_endpoint}): Connection error - {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching Radarr movie details ({api_endpoint}): {e}", exc_info=True)
        return None

# ... (other radarr service functions if any) ...
