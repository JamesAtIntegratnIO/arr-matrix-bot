import asyncio # Added
import aiohttp  # Added
import logging
from urllib.parse import urljoin
import ssl      # Added for verify_tls handling

logger = logging.getLogger(__name__)

# Default timeout in seconds - can be adjusted
REQUEST_TIMEOUT = 15

# --- Helper for TLS verification ---
def _get_ssl_context(verify_tls: bool):
    if verify_tls:
        return None # Use default SSL context which verifies
    else:
        # Create a context that does NOT verify certificates
        # WARNING: Use with caution, disables security checks.
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        logger.warning("TLS verification is DISABLED for Sonarr requests.")
        return context

async def search_sonarr_lookup(query: str, sonarr_url: str, api_key: str, verify_tls: bool = True) -> list | None:
    """
    (Async) Searches Sonarr for potential series matches using the /series/lookup endpoint.
    """
    if not sonarr_url or not api_key:
        logger.error("Sonarr URL or API Key is not configured.")
        return None

    if not sonarr_url.startswith(('http://', 'https://')):
         logger.warning(f"Sonarr URL '{sonarr_url}' is missing scheme, defaulting to http://")
         sonarr_url = 'http://' + sonarr_url

    api_endpoint = urljoin(sonarr_url, '/api/v3/series/lookup')
    headers = {'X-Api-Key': api_key}
    params = {'term': query}
    ssl_context = _get_ssl_context(verify_tls)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
            logger.info(f"Sending async request to Sonarr lookup: {api_endpoint} with term: '{query}'")
            async with session.get(api_endpoint, headers=headers, params=params, ssl=ssl_context) as response:
                response.raise_for_status() # Raise exception for 4xx/5xx status
                try:
                    results = await response.json()
                    if isinstance(results, list):
                        logger.info(f"Sonarr lookup successful. Found {len(results)} potential matches for '{query}'.")
                        return results
                    else:
                        logger.error(f"Sonarr API ({api_endpoint}) returned unexpected data type: {type(results)}. Expected list.")
                        return None
                except aiohttp.ContentTypeError: # Handles JSON decoding errors in aiohttp
                    body_preview = await response.text()
                    logger.error(f"Failed to decode JSON response from Sonarr ({api_endpoint}). Status: {response.status}, Body: {body_preview[:200]}...")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Error communicating with Sonarr API ({api_endpoint}): Request timed out after {REQUEST_TIMEOUT} seconds.")
        return None
    except aiohttp.ClientResponseError as e: # Handles HTTP status errors
        logger.error(f"Error communicating with Sonarr API ({api_endpoint}): HTTP {e.status} - {e.message}")
        # Attempt to log response body if available
        try:
            body_preview = await e.response.text()
            logger.error(f"Sonarr API Response Body (partial): {body_preview[:200]}...")
        except Exception:
            pass # Ignore errors reading body during error handling
        return None
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Error communicating with Sonarr API ({api_endpoint}): Connection error - {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Sonarr search ({api_endpoint}): {e}", exc_info=True)
        return None


async def get_sonarr_series_details(series_id: int, sonarr_url: str, api_key: str, verify_tls: bool = True) -> dict | None:
    """
    (Async) Retrieves the full details for a specific series already in Sonarr.
    """
    if not sonarr_url or not api_key:
        logger.error("Sonarr URL or API Key is not configured for fetching details.")
        return None
    if not series_id:
        logger.error("Cannot fetch Sonarr series details: Invalid series_id provided.")
        return None

    if not sonarr_url.startswith(('http://', 'https://')):
         sonarr_url = 'http://' + sonarr_url

    api_endpoint = urljoin(sonarr_url, f'/api/v3/series/{series_id}')
    headers = {'X-Api-Key': api_key}
    ssl_context = _get_ssl_context(verify_tls)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
            logger.info(f"Requesting async details for Sonarr series ID: {series_id} from {api_endpoint}")
            async with session.get(api_endpoint, headers=headers, ssl=ssl_context) as response:
                response.raise_for_status()
                try:
                    details = await response.json()
                    if isinstance(details, dict):
                        logger.info(f"Successfully retrieved details for Sonarr series ID: {series_id}")
                        return details
                    else:
                        logger.error(f"Sonarr details API ({api_endpoint}) returned unexpected data type: {type(details)}. Expected dict.")
                        return None
                except aiohttp.ContentTypeError:
                    body_preview = await response.text()
                    logger.error(f"Failed to decode JSON response from Sonarr details API ({api_endpoint}). Status: {response.status}, Body: {body_preview[:200]}...")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Error getting details for Sonarr series ID {series_id} ({api_endpoint}): Request timed out after {REQUEST_TIMEOUT} seconds.")
        return None
    except aiohttp.ClientResponseError as e:
        logger.error(f"Error getting details for Sonarr series ID {series_id} ({api_endpoint}): HTTP {e.status} - {e.message}")
        try:
            body_preview = await e.response.text()
            logger.error(f"Sonarr Details API Response Body (partial): {body_preview[:200]}...")
        except Exception:
            pass
        return None
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Error getting details for Sonarr series ID {series_id} ({api_endpoint}): Connection error - {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching Sonarr series details ({api_endpoint}): {e}", exc_info=True)
        return None

# --- NEW FUNCTION ---
async def get_sonarr_episode_details(episode_id: int, sonarr_url: str, api_key: str, verify_tls: bool = True) -> dict | None:
    """
    (Async) Retrieves the full details for a specific episode already in Sonarr.

    Args:
        episode_id: The Sonarr internal ID of the episode.
        sonarr_url: The base URL of the Sonarr instance.
        api_key: The Sonarr API key.
        verify_tls: Whether to verify the TLS certificate of the Sonarr instance.

    Returns:
        A dictionary containing the episode details if successful, None otherwise.
        The dictionary includes nested 'series' information.
    """
    if not sonarr_url or not api_key:
        logger.error("Sonarr URL or API Key is not configured for fetching episode details.")
        return None
    if not episode_id:
        logger.error("Cannot fetch Sonarr episode details: Invalid episode_id provided.")
        return None

    if not sonarr_url.startswith(('http://', 'https://')):
         sonarr_url = 'http://' + sonarr_url

    # Construct the specific episode endpoint URL
    api_endpoint = urljoin(sonarr_url, f'/api/v3/episode/{episode_id}')
    headers = {'X-Api-Key': api_key}
    ssl_context = _get_ssl_context(verify_tls)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
            logger.info(f"Requesting async details for Sonarr episode ID: {episode_id} from {api_endpoint}")
            async with session.get(api_endpoint, headers=headers, ssl=ssl_context) as response:
                response.raise_for_status() # Check for HTTP errors

                try:
                    details = await response.json()
                    # The episode endpoint returns the episode object directly, often including a nested 'series' object
                    if isinstance(details, dict) and 'series' in details:
                        logger.info(f"Successfully retrieved details for Sonarr episode ID: {episode_id} (Title: '{details.get('title', 'N/A')}')")
                        return details
                    elif isinstance(details, dict):
                         logger.warning(f"Sonarr episode details API ({api_endpoint}) returned a dict, but missing 'series' info. Episode ID: {episode_id}")
                         return details # Return partial data? Or None? Decide based on need. Returning dict for now.
                    else:
                        logger.error(f"Sonarr episode details API ({api_endpoint}) returned unexpected data type: {type(details)}. Expected dict.")
                        return None
                except aiohttp.ContentTypeError:
                    body_preview = await response.text()
                    logger.error(f"Failed to decode JSON response from Sonarr episode details API ({api_endpoint}). Status: {response.status}, Body: {body_preview[:200]}...")
                    return None

    except asyncio.TimeoutError:
        logger.error(f"Error getting details for Sonarr episode ID {episode_id} ({api_endpoint}): Request timed out after {REQUEST_TIMEOUT} seconds.")
        return None
    except aiohttp.ClientResponseError as e: # Handles HTTP status errors
        logger.error(f"Error getting details for Sonarr episode ID {episode_id} ({api_endpoint}): HTTP {e.status} - {e.message}")
        try:
            body_preview = await e.response.text()
            logger.error(f"Sonarr Episode Details API Response Body (partial): {body_preview[:200]}...")
        except Exception:
            pass
        return None
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Error getting details for Sonarr episode ID {episode_id} ({api_endpoint}): Connection error - {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching Sonarr episode details ({api_endpoint}): {e}", exc_info=True)
        return None
# --- END NEW FUNCTION ---


async def test_sonarr_connection(sonarr_url: str, api_key: str, verify_tls: bool = True) -> bool:
    """(Async) Tests the connection and authentication to the Sonarr API using /system/status."""
    if not sonarr_url or not api_key:
        logger.error("Cannot test Sonarr connection: URL or API Key is missing.")
        return False

    if not sonarr_url.startswith(('http://', 'https://')):
         sonarr_url = 'http://' + sonarr_url

    api_endpoint = urljoin(sonarr_url, '/api/v3/system/status')
    headers = {'X-Api-Key': api_key}
    ssl_context = _get_ssl_context(verify_tls)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session: # Shorter timeout for test
            logger.info(f"Testing async Sonarr connection to {api_endpoint}...")
            async with session.get(api_endpoint, headers=headers, ssl=ssl_context) as response:
                response.raise_for_status()
                # Optionally check response content if needed
                # status_data = await response.json()
                logger.info(f"Sonarr connection test successful ({api_endpoint}).")
                return True
    except asyncio.TimeoutError:
        logger.error(f"Sonarr connection test failed: Timeout connecting to {api_endpoint}")
        return False
    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            logger.error(f"Sonarr connection test failed: Authentication error (Invalid API Key?). Status: 401 ({api_endpoint})")
        else:
            logger.error(f"Sonarr connection test failed: HTTP error {e.status} connecting to {api_endpoint}")
        return False
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Sonarr connection test failed ({api_endpoint}): Connection error - {e}")
        return False
    except Exception as e:
         logger.error(f"An unexpected error occurred during Sonarr connection test ({api_endpoint}): {e}", exc_info=True)
         return False
