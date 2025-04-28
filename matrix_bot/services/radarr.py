import requests
import logging
from urllib.parse import urljoin
from typing import Optional, List, Dict, Any # Add typing

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15

def search_radarr_movie(query: str, radarr_url: str, api_key: str) -> Optional[List[Dict[str, Any]]]:
    """Searches Radarr using /movie/lookup."""
    # ... (Keep existing search_radarr_movie function as is) ...
    if not radarr_url or not api_key: logger.error("Radarr URL/API Key missing."); return None
    if not radarr_url.startswith(('http://', 'https://')): radarr_url = 'http://' + radarr_url
    api_endpoint = urljoin(radarr_url, '/api/v3/movie/lookup')
    headers = {'X-Api-Key': api_key}; params = {'term': query}
    try:
        logger.info(f"Sending request to Radarr lookup: {api_endpoint} with term: '{query}'")
        response = requests.get(api_endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT); response.raise_for_status()
        try:
            results = response.json()
            if isinstance(results, list): logger.info(f"Radarr lookup successful. Found {len(results)} matches for '{query}'."); return results
            else: logger.error(f"Radarr API ({api_endpoint}) returned unexpected type: {type(results)}."); return None
        except requests.exceptions.JSONDecodeError: logger.error(f"Failed to decode JSON from Radarr ({api_endpoint}). Status: {response.status_code}, Body: {response.text[:200]}..."); return None
    except requests.exceptions.Timeout: logger.error(f"Error communicating with Radarr ({api_endpoint}): Timeout after {REQUEST_TIMEOUT}s."); return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with Radarr ({api_endpoint}): {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None: logger.error(f"Radarr API Response (partial): {e.response.text[:200]}...")
        return None
    except Exception as e: logger.error(f"Unexpected error during Radarr search ({api_endpoint}): {e}"); return None


# --- NEW: Lookup by TMDb ID ---
def lookup_radarr_movie_by_tmdb(tmdb_id: int, radarr_url: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Looks up a single movie in Radarr by its TMDb ID."""
    lookup_term = f"tmdb:{tmdb_id}"
    results = search_radarr_movie(lookup_term, radarr_url, api_key) # Reuse the search function

    if results is None:
        # Error already logged by search_radarr_movie
        return None
    elif not results:
        logger.info(f"Radarr lookup found no movie matching TMDb ID {tmdb_id}.")
        return None
    else:
        # TMDb ID lookups should ideally return one primary result
        if len(results) > 1:
             logger.warning(f"Radarr lookup for TMDb ID {tmdb_id} returned {len(results)} results. Using the first one.")
        return results[0]

# --- NEW: Get Radarr Movie Details ---
def get_radarr_movie_details(radarr_movie_id: int, radarr_url: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Gets detailed information for a specific movie already in Radarr by its Radarr ID."""
    if not radarr_url or not api_key: logger.error("Radarr URL/API Key missing."); return None
    if not radarr_url.startswith(('http://', 'https://')): radarr_url = 'http://' + radarr_url

    # Construct the endpoint for a specific movie ID
    api_endpoint = urljoin(radarr_url, f'/api/v3/movie/{radarr_movie_id}')
    headers = {'X-Api-Key': api_key}

    try:
        logger.info(f"Requesting details for Radarr movie ID: {radarr_movie_id} from {api_endpoint}")
        response = requests.get(api_endpoint, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        try:
            details = response.json()
            if isinstance(details, dict):
                 logger.info(f"Successfully retrieved details for Radarr movie ID: {radarr_movie_id}")
                 return details
            else:
                 logger.error(f"Radarr details endpoint ({api_endpoint}) returned unexpected type: {type(details)}.")
                 return None
        except requests.exceptions.JSONDecodeError:
            logger.error(f"Failed to decode JSON details from Radarr ({api_endpoint}). Status: {response.status_code}, Body: {response.text[:200]}...")
            return None
    except requests.exceptions.Timeout: logger.error(f"Error getting Radarr details ({api_endpoint}): Timeout after {REQUEST_TIMEOUT}s."); return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting Radarr details ({api_endpoint}): {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None: logger.error(f"Radarr API Response (partial): {e.response.text[:200]}...")
        return None
    except Exception as e: logger.error(f"Unexpected error getting Radarr details ({api_endpoint}): {e}"); return None


def test_radarr_connection(radarr_url: str, api_key: str) -> bool:
    """Tests the connection and authentication to the Radarr API."""
    # ... (Keep existing test_radarr_connection function as is) ...
    if not radarr_url or not api_key: logger.error("Cannot test Radarr: URL/API Key missing."); return False
    if not radarr_url.startswith(('http://', 'https://')): radarr_url = 'http://' + radarr_url
    api_endpoint = urljoin(radarr_url, '/api/v3/system/status'); headers = {'X-Api-Key': api_key}
    try:
        logger.info(f"Testing Radarr connection to {api_endpoint}...")
        response = requests.get(api_endpoint, headers=headers, timeout=10); response.raise_for_status()
        logger.info(f"Radarr connection test successful ({api_endpoint})."); return True
    except requests.exceptions.Timeout: logger.error(f"Radarr test failed: Timeout connecting to {api_endpoint}"); return False
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401: logger.error(f"Radarr test failed: Auth error (Invalid API Key?). Status: 401 ({api_endpoint})")
        else: logger.error(f"Radarr test failed: HTTP error {e.response.status_code} ({api_endpoint})")
        return False
    except requests.exceptions.RequestException as e: logger.error(f"Radarr test failed ({api_endpoint}): {e}"); return False
    except Exception as e: logger.error(f"Unexpected error during Radarr test ({api_endpoint}): {e}"); return False
