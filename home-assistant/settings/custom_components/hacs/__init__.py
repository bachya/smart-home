"""
Custom element manager for community created elements.

For more details about this integration, please refer to the documentation at
https://hacs.xyz/
"""

import voluptuous as vol
from aiogithubapi import AIOGitHub
from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.const import __version__ as HAVERSION
from homeassistant.components.lovelace import system_health_info
from homeassistant.exceptions import ConfigEntryNotReady, ServiceNotFound
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_call_later

from custom_components.hacs.configuration_schema import (
    hacs_base_config_schema,
    hacs_config_option_schema,
)
from custom_components.hacs.const import DOMAIN, ELEMENT_TYPES, STARTUP, VERSION
from custom_components.hacs.constrains import check_constans, check_requirements
from custom_components.hacs.hacsbase.configuration import Configuration
from custom_components.hacs.hacsbase.data import HacsData
from custom_components.hacs.setup import (
    add_sensor,
    load_hacs_repository,
    setup_frontend,
)

from custom_components.hacs.globals import get_hacs

from custom_components.hacs.helpers.network import internet_connectivity_check

SCHEMA = hacs_base_config_schema()
SCHEMA[vol.Optional("options")] = hacs_config_option_schema()
CONFIG_SCHEMA = vol.Schema({DOMAIN: SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up this integration using yaml."""
    hacs = get_hacs()
    if DOMAIN not in config:
        return True
    hass.data[DOMAIN] = config
    hacs.hass = hass
    hacs.session = async_create_clientsession(hass)
    hacs.configuration = Configuration.from_dict(
        config[DOMAIN], config[DOMAIN].get("options")
    )
    hacs.configuration.config = config
    hacs.configuration.config_type = "yaml"
    await startup_wrapper_for_yaml()
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
        )
    )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up this integration using UI."""
    hacs = get_hacs()
    conf = hass.data.get(DOMAIN)
    if config_entry.source == config_entries.SOURCE_IMPORT:
        if conf is None:
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
        return False
    hacs.hass = hass
    hacs.session = async_create_clientsession(hass)
    hacs.configuration = Configuration.from_dict(
        config_entry.data, config_entry.options
    )
    hacs.configuration.config_type = "flow"
    hacs.configuration.config_entry = config_entry
    config_entry.add_update_listener(reload_hacs)
    startup_result = await hacs_startup()
    if not startup_result:
        hacs.system.disabled = True
        raise ConfigEntryNotReady
    hacs.system.disabled = False
    return startup_result


async def startup_wrapper_for_yaml():
    """Startup wrapper for yaml config."""
    hacs = get_hacs()
    startup_result = await hacs_startup()
    if not startup_result:
        hacs.system.disabled = True
        hacs.hass.components.frontend.async_remove_panel(
            hacs.configuration.sidepanel_title.lower()
            .replace(" ", "_")
            .replace("-", "_")
        )
        hacs.logger.info("Could not setup HACS, trying again in 15 min")
        async_call_later(hacs.hass, 900, startup_wrapper_for_yaml())
        return
    hacs.system.disabled = False


async def hacs_startup():
    """HACS startup tasks."""
    hacs = get_hacs()
    if not check_requirements():
        return False
    if hacs.configuration.debug:
        try:
            await hacs.hass.services.async_call(
                "logger", "set_level", {"hacs": "debug"}
            )
        except ServiceNotFound:
            hacs.logger.error(
                "Could not set logging level to debug, logger is not enabled"
            )

    lovelace_info = await system_health_info(hacs.hass)
    hacs.logger.debug(f"Configuration type: {hacs.configuration.config_type}")
    hacs.version = VERSION
    hacs.logger.info(STARTUP)
    hacs.system.config_path = hacs.hass.config.path()
    hacs.system.ha_version = HAVERSION

    hacs.system.lovelace_mode = lovelace_info.get("mode", "yaml")
    hacs.system.disabled = False
    hacs.github = AIOGitHub(
        hacs.configuration.token, async_create_clientsession(hacs.hass)
    )
    hacs.data = HacsData()

    # Check HACS Constrains
    if not await hacs.hass.async_add_executor_job(check_constans):
        if hacs.configuration.config_type == "flow":
            if hacs.configuration.config_entry is not None:
                await async_remove_entry(hacs.hass, hacs.configuration.config_entry)
        return False

    # Set up frontend
    await setup_frontend()

    if not await hacs.hass.async_add_executor_job(internet_connectivity_check):
        hacs.logger.critical("No network connectivity")
        return False

    # Load HACS
    if not await load_hacs_repository():
        if hacs.configuration.config_type == "flow":
            if hacs.configuration.config_entry is not None:
                await async_remove_entry(hacs.hass, hacs.configuration.config_entry)
        return False

    # Restore from storefiles
    if not await hacs.data.restore():
        hacs_repo = hacs.get_by_name("hacs/integration")
        hacs_repo.pending_restart = True
        if hacs.configuration.config_type == "flow":
            if hacs.configuration.config_entry is not None:
                await async_remove_entry(hacs.hass, hacs.configuration.config_entry)
        return False

    # Add aditional categories
    hacs.common.categories = ELEMENT_TYPES
    if hacs.configuration.appdaemon:
        hacs.common.categories.append("appdaemon")
    if hacs.configuration.netdaemon:
        hacs.common.categories.append("netdaemon")
    if hacs.configuration.python_script:
        hacs.configuration.python_script = False
        if hacs.configuration.config_type == "yaml":
            hacs.logger.warning(
                "Configuration option 'python_script' is deprecated and you should remove it from your configuration, HACS will know if you use 'python_script' in your Home Assistant configuration, this option will be removed in a future release."
            )
    if hacs.configuration.theme:
        hacs.configuration.theme = False
        if hacs.configuration.config_type == "yaml":
            hacs.logger.warning(
                "Configuration option 'theme' is deprecated and you should remove it from your configuration, HACS will know if you use 'theme' in your Home Assistant configuration, this option will be removed in a future release."
            )

    # Setup startup tasks
    if hacs.configuration.config_type == "yaml":
        hacs.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, hacs.startup_tasks())
    else:
        async_call_later(hacs.hass, 5, hacs.startup_tasks())

    # Show the configuration
    hacs.configuration.print()

    # Set up sensor
    await hacs.hass.async_add_executor_job(add_sensor)

    # Mischief managed!
    return True


async def async_remove_entry(hass, config_entry):
    """Handle removal of an entry."""
    hacs = get_hacs()
    hacs.logger.info("Disabling HACS")
    hacs.logger.info("Removing recuring tasks")
    for task in hacs.recuring_tasks:
        task()
    hacs.logger.info("Removing sensor")
    try:
        await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    except ValueError:
        pass
    hacs.logger.info("Removing sidepanel")
    try:
        hass.components.frontend.async_remove_panel("hacs")
    except AttributeError:
        pass
    hacs.system.disabled = True
    hacs.logger.info("HACS is now disabled")


async def reload_hacs(hass, config_entry):
    """Reload HACS."""
    await async_remove_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
