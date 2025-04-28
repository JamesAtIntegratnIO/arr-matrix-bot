import logging
from typing import Tuple, Dict, Optional
import simplematrixbotlib as botlib

# Assuming services modules have ping functions
from ..services import sonarr as sonarr_service
from ..services import radarr as radarr_service
from .. import config as config_module

logger = logging.getLogger(__name__)

async def check_matrix_connection(bot: botlib.Bot) -> Tuple[bool, str]:
    """Checks if the bot can communicate with the Matrix homeserver."""
    try:
        # A simple API call to verify connection and token
        await bot.api.async_client.get_displayname(bot.user_id)
        logger.info("Matrix connection check successful.")
        return True, "OK"
    except Exception as e:
        logger.error(f"Matrix connection check failed: {e}", exc_info=True)
        return False, f"Failed: {type(e).__name__}"

async def check_sonarr_connection(config: config_module.MyConfig) -> Tuple[bool, str]:
    """Checks if Sonarr is reachable and API key is valid."""
    if not config.sonarr_url or not config.sonarr_api_key:
        return False, "Not Configured"
    try:
        success = await sonarr_service.ping_sonarr(
            config.sonarr_url, config.sonarr_api_key, verify_tls=config.verify_tls
        )
        if success:
            logger.info("Sonarr connection check successful.")
            return True, "OK"
        else:
            # ping_sonarr might need more specific error reporting if needed
            logger.warning("Sonarr connection check failed (ping returned False).")
            return False, "Ping Failed"
    except Exception as e:
        logger.error(f"Sonarr connection check failed with exception: {e}", exc_info=True)
        return False, f"Error: {type(e).__name__}"

async def check_radarr_connection(config: config_module.MyConfig) -> Tuple[bool, str]:
    """Checks if Radarr is reachable and API key is valid."""
    if not config.radarr_url or not config.radarr_api_key:
        return False, "Not Configured"
    try:
        success = await radarr_service.ping_radarr(
            config.radarr_url, config.radarr_api_key, verify_tls=config.verify_tls
        )
        if success:
            logger.info("Radarr connection check successful.")
            return True, "OK"
        else:
            logger.warning("Radarr connection check failed (ping returned False).")
            return False, "Ping Failed"
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
    # Add other services here if needed
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
        if not success and message != "Not Configured": # Treat actual failures as overall failure
            overall_ok = False

    html_body += "</ul>"
    if overall_ok:
        plain_body += "\n\nOverall Status: OK"
        html_body += "<p><strong>Overall Status: OK</strong></p>"
    else:
        plain_body += "\n\nOverall Status: Issues Detected"
        html_body += "<p><strong>Overall Status: Issues Detected</strong></p>"

    return plain_body, html_body
