import json
import logging
import sys
import simplematrixbotlib as botlib

logger = logging.getLogger(__name__)

creds = None
config_instance = None

class MyConfig:
    """Holds bot configuration."""
    def __init__(self, data: dict):
        self.matrix_homeserver: str = data.get("matrix_homeserver", "")
        self.matrix_user: str = data.get("matrix_user", "")
        self.matrix_password: str = data.get("matrix_password", "")
        self.target_room_id: str = data.get("target_room_id", "")
        self.command_prefix: str = data.get("command_prefix", "!")
        self.sonarr_url: str = data.get("sonarr_url", "")
        self.sonarr_api_key: str = data.get("sonarr_api_key", "")
        self.radarr_url: str = data.get("radarr_url", "")
        self.radarr_api_key: str = data.get("radarr_api_key", "")
        self.tvdb_base_url: str = data.get("tvdb_base_url", "https://api4.thetvdb.com/v4")
        self.tvdb_api_key: str = data.get("tvdb_api_key", "")
        self.verify_tls: bool = data.get("verify_tls", True)
        # --- Webhook Config ---
        self.webhook_host: str = data.get("webhook_host", "0.0.0.0")
        self.webhook_port: int = data.get("webhook_port", 9095)
        # ----------------------

        if not self.matrix_homeserver or not self.matrix_user or not self.matrix_password:
             logger.critical("Matrix credentials missing in config.")
             global config_instance; config_instance = None
             raise ValueError("Matrix credentials missing.")
        if not self.command_prefix or len(self.command_prefix) != 1:
            logger.warning(f"Invalid command prefix '{self.command_prefix}'. Defaulting to '!'")
            self.command_prefix = "!"
        # Optional: Validate webhook port is integer
        if not isinstance(self.webhook_port, int) or not (0 < self.webhook_port < 65536):
            logger.warning(f"Invalid webhook port '{self.webhook_port}'. Defaulting to 9095.")
            self.webhook_port = 9095


def load_config(path: str) -> MyConfig | None:
    """Loads configuration from a JSON file."""
    global creds, config_instance
    try:
        logger.info(f"Attempting to load configuration from: {path}") # Added logging
        with open(path, 'r') as f: config_data = json.load(f)
        config_instance = MyConfig(config_data)
        creds = botlib.Creds(
            config_instance.matrix_homeserver, config_instance.matrix_user, config_instance.matrix_password
        )
        logger.info("Configuration loaded and credentials created successfully.")
        return config_instance
    except FileNotFoundError: logger.critical(f"Config file not found: {path}"); creds = None; config_instance = None; return None
    except json.JSONDecodeError: logger.critical(f"Failed to decode JSON config: {path}"); creds = None; config_instance = None; return None
    except ValueError as e: logger.critical(f"Config validation failed: {e}"); creds = None; config_instance = None; return None
    except Exception as e: logger.critical(f"Unexpected error loading config: {e}"); creds = None; config_instance = None; return None

# Load config immediately on import
# --- CHANGE THIS LINE ---
load_config('/config/config.json')
# --- END CHANGE ---