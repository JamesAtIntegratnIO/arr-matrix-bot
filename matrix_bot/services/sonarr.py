import requests
import logging
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Default timeout in seconds - can be adjusted
REQUEST_TIMEOUT = 15

def search_sonarr_lookup(query: str, sonarr_url: str, api_key: str) -> list | None:
    """
    Searches Sonarr for potential series matches using the /series/lookup endpoint.
    [... existing docstring ...]
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

    try:
        logger.info(f"Sending request to Sonarr lookup: {api_endpoint} with term: '{query}'")
        response = requests.get(api_endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        try:
            results = response.json()
            if isinstance(results, list):
                logger.info(f"Sonarr lookup successful. Found {len(results)} potential matches for '{query}'.")
                return results
            else:
                logger.error(f"Sonarr API ({api_endpoint}) returned unexpected data type: {type(results)}. Expected list.")
                return None
        except requests.exceptions.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from Sonarr ({api_endpoint}). Status: {response.status_code}, Body: {response.text[:200]}...")
            return None
    except requests.exceptions.Timeout:
        logger.error(f"Error communicating with Sonarr API ({api_endpoint}): Read timed out after {REQUEST_TIMEOUT} seconds.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with Sonarr API ({api_endpoint}): {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
             logger.error(f"Sonarr API Response Body (partial): {e.response.text[:200]}...")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Sonarr search ({api_endpoint}): {e}")
        return None

# --- NEW FUNCTION ---
def get_sonarr_series_details(series_id: int, sonarr_url: str, api_key: str) -> dict | None:
    """
    Retrieves the full details for a specific series already in Sonarr.

    Args:
        series_id: The Sonarr internal ID of the series.
        sonarr_url: The base URL of the Sonarr instance.
        api_key: The Sonarr API key.

    Returns:
        A dictionary containing the series details if successful, None otherwise.
    """
    if not sonarr_url or not api_key:
        logger.error("Sonarr URL or API Key is not configured for fetching details.")
        return None
    if not series_id:
        logger.error("Cannot fetch Sonarr series details: Invalid series_id provided.")
        return None

    if not sonarr_url.startswith(('http://', 'https://')):
         sonarr_url = 'http://' + sonarr_url

    # Construct the specific series endpoint URL
    api_endpoint = urljoin(sonarr_url, f'/api/v3/series/{series_id}')
    headers = {'X-Api-Key': api_key}

    try:
        logger.info(f"Requesting details for Sonarr series ID: {series_id} from {api_endpoint}")
        response = requests.get(api_endpoint, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        try:
            details = response.json()
            if isinstance(details, dict):
                logger.info(f"Successfully retrieved details for Sonarr series ID: {series_id}")
                return details
            else:
                logger.error(f"Sonarr details API ({api_endpoint}) returned unexpected data type: {type(details)}. Expected dict.")
                return None
        except requests.exceptions.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from Sonarr details API ({api_endpoint}). Status: {response.status_code}, Body: {response.text[:200]}...")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"Error getting details for Sonarr series ID {series_id} ({api_endpoint}): Read timed out after {REQUEST_TIMEOUT} seconds.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting details for Sonarr series ID {series_id} ({api_endpoint}): {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
             logger.error(f"Sonarr Details API Response Body (partial): {e.response.text[:200]}...")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching Sonarr series details ({api_endpoint}): {e}")
        return None
# --- END NEW FUNCTION ---


def test_sonarr_connection(sonarr_url: str, api_key: str) -> bool:
    """Tests the connection and authentication to the Sonarr API using /system/status."""
    # [... existing code ...]
    if not sonarr_url or not api_key:
        logger.error("Cannot test Sonarr connection: URL or API Key is missing.")
        return False

    if not sonarr_url.startswith(('http://', 'https://')):
         sonarr_url = 'http://' + sonarr_url

    api_endpoint = urljoin(sonarr_url, '/api/v3/system/status')
    headers = {'X-Api-Key': api_key}

    try:
        logger.info(f"Testing Sonarr connection to {api_endpoint}...")
        response = requests.get(api_endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"Sonarr connection test successful ({api_endpoint}).")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Sonarr connection test failed: Timeout connecting to {api_endpoint}")
        return False
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error(f"Sonarr connection test failed: Authentication error (Invalid API Key?). Status: 401 ({api_endpoint})")
        else:
            logger.error(f"Sonarr connection test failed: HTTP error {e.response.status_code} connecting to {api_endpoint}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Sonarr connection test failed ({api_endpoint}): {e}")
        return False
    except Exception as e:
         logger.error(f"An unexpected error occurred during Sonarr connection test ({api_endpoint}): {e}")
         return False
