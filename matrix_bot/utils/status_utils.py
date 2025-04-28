import logging
from typing import Tuple, Dict, Optional
import simplematrixbotlib as botlib
import asyncio

# Assuming services modules have appropriate functions
from ..services import sonarr as sonarr_service
from ..services import radarr as radarr_service
from .. import config as config_module

logger = logging.getLogger(__name__)

async def check_matrix_connection(bot: botlib.Bot) -> Tuple[bool, str]:
    """Checks if the bot can communicate with the Matrix homeserver."""
    try:
        # FIX 1: Use bot.api.async_client.user_id
        user_id_to_check = bot.api.async_client.user_id
        await bot.api.async_client.get_displayname(user_id_to_check)
        logger.info("Matrix connection check successful.")
        return True, "OK"
    except asyncio.TimeoutError:
         logger.error("Matrix connection check failed: Timeout")
         return False, "Failed: Timeout"
    except AttributeError as e:
        # Catch if async_client or user_id isn't ready yet during early startup?
        logger.error(f"Matrix connection check failed accessing attributes: {e}", exc_info=True)
        return False, f"Failed: Attribute Error ({e})"
    except Exception as e:
        logger.error(f"Matrix connection check failed: {e}", exc_info=True)
        return False, f"Failed: {type(e).__name__}"

async def check_sonarr_connection(config: config_module.MyConfig) -> Tuple[bool, str]:
    """Checks if Sonarr is reachable and API key is valid using test_sonarr_connection."""
    if not config.sonarr_url or not config.sonarr_api_key:
        return False, "Not Configured"
    try:
        # FIX 2: Use test_sonarr_connection
        success = await sonarr_service.test_sonarr_connection(
            config.sonarr_url, config.sonarr_api_key, verify_tls=config.verify_tls
        )
        if success:
            logger.info("Sonarr connection check successful.")
            return True, "OK"
        else:
            logger.warning("Sonarr connection check failed (test_sonarr_connection returned False).")
            return False, "Failed"
    except AttributeError:
         # This error should no longer happen if test_sonarr_connection exists
         logger.error("Sonarr service module does not have 'test_sonarr_connection'.")
         return False, "Check Function Missing"
    except Exception as e:
        logger.error(f"Sonarr connection check failed with exception: {e}", exc_info=True)
        return False, f"Error: {type(e).__name__}"

async def check_radarr_connection(config: config_module.MyConfig) -> Tuple[bool, str]:
    """Checks if Radarr is reachable and API key is valid using ping_radarr."""
    if not config.radarr_url or not config.radarr_api_key:
        return False, "Not Configured"
    try:
        # Ensure ping_radarr exists in services/radarr.py (User Action Required if error persists)
        success = await radarr_service.ping_radarr(
            config.radarr_url, config.radarr_api_key, verify_tls=config.verify_tls
        )
        if success:
            logger.info("Radarr connection check successful.")
            return True, "OK"
        else:
            logger.warning("Radarr connection check failed (ping_radarr returned False).")
            return False, "Failed"
    except AttributeError:
         # This error means ping_radarr is missing from services/radarr.py
         logger.error("Radarr service module does not have a 'ping_radarr' async function.")
         return False, "Check Function Missing"
    except Exception as e:
        logger.error(f"Radarr connection check failed with exception: {e}", exc_info=True)
        return False, f"Error: {type(e).__name__}"

async def check_all_services(bot: botlib.Bot, config: config_module.MyConfig) -> Dict[str, Tuple[bool, str]]:
    """Performs connectivity checks for all configured services."""
    logger.info("Performing status check for all services...")
    results = {}
    results["Matrix"] = await check_matrix_connection(bot)
    results["Sonarr"] = await check_sonarr_connection(config)
    results["Radarr"] = await check_radarr_connection(config)
    logger.info("Finished status check.")
    return results

def format_status_report(status_results: Dict[str, Tuple[bool, str]]) -> Tuple[str, str]:
    """Formats the status check results into plain text and HTML."""
    plain_body = "Service Status Report:\n"
    html_body = "<h3>Service Status Report</h3><ul>"
    overall_ok = True

    for service, (success, message) in status_results.items():
        emoji = "✅" if success else "❌"
        plain_body += f"\n{emoji} {service}: {message}"
        html_body += f"<li>{emoji} <strong>{service}:</strong> {message}</li>"
        if not success and message not in ["Not Configured"]:
            overall_ok = False

    html_body += "</ul>"
    if overall_ok:
        plain_body += "\n\nOverall Status: OK"
        html_body += "<p><strong>Overall Status: OK</strong></p>"
    else:
        plain_body += "\n\nOverall Status: Issues Detected"
        html_body += "<p><strong>Overall Status: Issues Detected</strong></p>"

    return plain_body, html_body