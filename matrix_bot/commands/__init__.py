import logging
from typing import Dict

# Import command modules
from . import help as help_cmd
from . import sonarr as sonarr_cmd
from . import radarr as radarr_cmd
from . import status as status_cmd
from . import echo as echo_cmd

logger = logging.getLogger(__name__)

def register_all(bot, config, prefix):
    """
    Registers all defined command handlers and builds the help registry.
    """
    logger.info("Initializing command registration...")

    # --- Help Registry Setup ---
    # Create the central dictionary to hold help text for all commands
    help_registry: Dict[str, Dict[str, str]] = {}
    logger.info("Created help registry dictionary.")

    # --- Register Help Text from Each Module ---
    # Each module's register_help function adds its details to the registry
    logger.info("Registering help text from command modules...")
    try:
        help_cmd.register_help(help_registry, prefix)
        sonarr_cmd.register_help(help_registry, prefix)
        radarr_cmd.register_help(help_registry, prefix)
        status_cmd.register_help(help_registry, prefix)
        echo_cmd.register_help(help_registry, prefix)
        # Add calls for other command modules here if they exist
        logger.info(f"Registered help text for commands: {', '.join(help_registry.keys())}")
    except AttributeError as e:
        logger.error(f"Error during help registration: A command module is likely missing its 'register_help' function. Details: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during help registration: {e}", exc_info=True)


    # --- Register Command Listeners ---
    # Pass the completed help_registry ONLY to the help command's listener registration
    logger.info("Registering command listeners...")
    try:
        # Help command needs the registry to display help
        help_cmd.register(bot, config, prefix, help_registry)

        # Other commands just need bot, config, prefix
        sonarr_cmd.register(bot, config, prefix)
        radarr_cmd.register(bot, config, prefix)
        status_cmd.register(bot, config, prefix)
        echo_cmd.register(bot, config, prefix)
        # Add calls for other command modules here
        logger.info("Command listeners registered.")
    except AttributeError as e:
         logger.error(f"Error registering command listener: A command module is likely missing its 'register' function. Details: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during command listener registration: {e}", exc_info=True)


    logger.info("Command registration process complete.")
