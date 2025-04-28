import logging
import simplematrixbotlib as botlib
from .. import config as config_module

# Import individual command modules
from . import help as help_cmd
from . import sonarr as sonarr_cmd
from . import radarr as radarr_cmd
from . import status as status_cmd
# Import other command modules here...

logger = logging.getLogger(__name__)

def register_all(bot: botlib.Bot, config: config_module.MyConfig, prefix: str):
    """Registers all known commands."""
    logger.info("Registering commands...")
    help_cmd.register(bot, config, prefix)
    sonarr_cmd.register(bot, config, prefix)
    radarr_cmd.register(bot, config, prefix)
    status_cmd.register(bot, config, prefix)
    # Register other commands here...
    logger.info("All commands registered.")
