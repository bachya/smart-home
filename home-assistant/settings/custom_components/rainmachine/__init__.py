"""Support for RainMachine devices."""
import asyncio
from datetime import timedelta
import logging

from regenmaschine import Client
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import verify_domain_control

from .config_flow import configured_instances
from .const import (
    DATA_CLIENT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DOMAIN,
    PROVISION_SETTINGS,
    RESTRICTIONS_CURRENT,
    RESTRICTIONS_UNIVERSAL,
)

_LOGGER = logging.getLogger(__name__)

DATA_LISTENER = "listener"

PROGRAM_UPDATE_TOPIC = f"{DOMAIN}_program_update"
SENSOR_UPDATE_TOPIC = f"{DOMAIN}_data_update"
ZONE_UPDATE_TOPIC = f"{DOMAIN}_zone_update"

CONF_CONTROLLERS = "controllers"
CONF_PROGRAM_ID = "program_id"
CONF_SECONDS = "seconds"
CONF_ZONE_ID = "zone_id"
CONF_ZONE_RUN_TIME = "zone_run_time"

DEFAULT_ATTRIBUTION = "Data provided by Green Electronics LLC"
DEFAULT_ICON = "mdi:water"
DEFAULT_ZONE_RUN = 60 * 10

SERVICE_ALTER_PROGRAM = vol.Schema({vol.Required(CONF_PROGRAM_ID): cv.positive_int})

SERVICE_ALTER_ZONE = vol.Schema({vol.Required(CONF_ZONE_ID): cv.positive_int})

SERVICE_PAUSE_WATERING = vol.Schema({vol.Required(CONF_SECONDS): cv.positive_int})

SERVICE_START_PROGRAM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PROGRAM_ID): cv.positive_int}
)

SERVICE_START_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_ID): cv.positive_int,
        vol.Optional(CONF_ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN): cv.positive_int,
    }
)

SERVICE_STOP_PROGRAM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PROGRAM_ID): cv.positive_int}
)

SERVICE_STOP_ZONE_SCHEMA = vol.Schema({vol.Required(CONF_ZONE_ID): cv.positive_int})

CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_ZONE_RUN_TIME): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONTROLLERS): vol.All(
                    cv.ensure_list, [CONTROLLER_SCHEMA]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the RainMachine component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    for controller in conf[CONF_CONTROLLERS]:
        if controller[CONF_IP_ADDRESS] in configured_instances(hass):
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=controller
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up RainMachine as config entry."""
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(websession)

    try:
        await client.load_local(
            config_entry.data[CONF_IP_ADDRESS],
            config_entry.data[CONF_PASSWORD],
            port=config_entry.data[CONF_PORT],
            ssl=config_entry.data[CONF_SSL],
        )
    except RainMachineError as err:
        _LOGGER.error("An error occurred: %s", err)
        raise ConfigEntryNotReady
    else:
        # regenmaschine can load multiple controllers at once, but we only grab the one
        # we loaded above:
        controller = next(iter(client.controllers.values()))

        rainmachine = RainMachine(
            hass,
            controller,
            config_entry.data.get(CONF_ZONE_RUN_TIME, DEFAULT_ZONE_RUN),
            config_entry.data[CONF_SCAN_INTERVAL],
        )

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = rainmachine

    for component in ("binary_sensor", "sensor", "switch"):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    @_verify_domain_control
    async def disable_program(call):
        """Disable a program."""
        await rainmachine.controller.programs.disable(call.data[CONF_PROGRAM_ID])
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    @_verify_domain_control
    async def disable_zone(call):
        """Disable a zone."""
        await rainmachine.controller.zones.disable(call.data[CONF_ZONE_ID])
        async_dispatcher_send(hass, ZONE_UPDATE_TOPIC)

    @_verify_domain_control
    async def enable_program(call):
        """Enable a program."""
        await rainmachine.controller.programs.enable(call.data[CONF_PROGRAM_ID])
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    @_verify_domain_control
    async def enable_zone(call):
        """Enable a zone."""
        await rainmachine.controller.zones.enable(call.data[CONF_ZONE_ID])
        async_dispatcher_send(hass, ZONE_UPDATE_TOPIC)

    @_verify_domain_control
    async def pause_watering(call):
        """Pause watering for a set number of seconds."""
        await rainmachine.controller.watering.pause_all(call.data[CONF_SECONDS])
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    @_verify_domain_control
    async def start_program(call):
        """Start a particular program."""
        await rainmachine.controller.programs.start(call.data[CONF_PROGRAM_ID])
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    @_verify_domain_control
    async def start_zone(call):
        """Start a particular zone for a certain amount of time."""
        await rainmachine.controller.zones.start(
            call.data[CONF_ZONE_ID], call.data[CONF_ZONE_RUN_TIME]
        )
        async_dispatcher_send(hass, ZONE_UPDATE_TOPIC)

    @_verify_domain_control
    async def stop_all(call):
        """Stop all watering."""
        await rainmachine.controller.watering.stop_all()
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    @_verify_domain_control
    async def stop_program(call):
        """Stop a program."""
        await rainmachine.controller.programs.stop(call.data[CONF_PROGRAM_ID])
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    @_verify_domain_control
    async def stop_zone(call):
        """Stop a zone."""
        await rainmachine.controller.zones.stop(call.data[CONF_ZONE_ID])
        async_dispatcher_send(hass, ZONE_UPDATE_TOPIC)

    @_verify_domain_control
    async def unpause_watering(call):
        """Unpause watering."""
        await rainmachine.controller.watering.unpause_all()
        async_dispatcher_send(hass, PROGRAM_UPDATE_TOPIC)

    for service, method, schema in [
        ("disable_program", disable_program, SERVICE_ALTER_PROGRAM),
        ("disable_zone", disable_zone, SERVICE_ALTER_ZONE),
        ("enable_program", enable_program, SERVICE_ALTER_PROGRAM),
        ("enable_zone", enable_zone, SERVICE_ALTER_ZONE),
        ("pause_watering", pause_watering, SERVICE_PAUSE_WATERING),
        ("start_program", start_program, SERVICE_START_PROGRAM_SCHEMA),
        ("start_zone", start_zone, SERVICE_START_ZONE_SCHEMA),
        ("stop_all", stop_all, {}),
        ("stop_program", stop_program, SERVICE_STOP_PROGRAM_SCHEMA),
        ("stop_zone", stop_zone, SERVICE_STOP_ZONE_SCHEMA),
        ("unpause_watering", unpause_watering, {}),
    ]:
        hass.services.async_register(DOMAIN, service, method, schema=schema)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an OpenUV config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    remove_listener()

    tasks = [
        hass.config_entries.async_forward_entry_unload(config_entry, component)
        for component in ("binary_sensor", "sensor", "switch")
    ]

    await asyncio.gather(*tasks)

    return True


class RainMachine:
    """Define a generic RainMachine object."""

    def __init__(self, hass, controller, default_zone_runtime, scan_interval):
        """Initialize."""
        self._async_unsub_dispatcher_connect = None
        self._scan_interval_seconds = scan_interval
        self.controller = controller
        self.data = {}
        self.default_zone_runtime = default_zone_runtime
        self.device_mac = controller.mac
        self.hass = hass

        self._api_category_count = {
            PROVISION_SETTINGS: 0,
            RESTRICTIONS_CURRENT: 0,
            RESTRICTIONS_UNIVERSAL: 0,
        }
        self._api_category_locks = {
            PROVISION_SETTINGS: asyncio.Lock(),
            RESTRICTIONS_CURRENT: asyncio.Lock(),
            RESTRICTIONS_UNIVERSAL: asyncio.Lock(),
        }

    async def _async_fetch_from_api(self, api_category):
        """Execute the appropriate coroutine to fetch particular data from the API."""
        if api_category == PROVISION_SETTINGS:
            data = await self.controller.provisioning.settings()
        elif api_category == RESTRICTIONS_CURRENT:
            data = await self.controller.restrictions.current()
        elif api_category == RESTRICTIONS_UNIVERSAL:
            data = await self.controller.restrictions.universal()

        return data

    async def _async_update_listener_action(self, now):
        """Define an async_track_time_interval action to update data."""
        await self.async_update()

    @callback
    def async_deregister_api_interest(self, api_category):
        """Decrement the number of entities with data needs from an API category."""
        # If this deregistration should leave us with no registration at all, remove the
        # time interval:
        if sum(self._api_category_count.values()) == 0:
            if self._async_unsub_dispatcher_connect:
                self._async_unsub_dispatcher_connect()
                self._async_unsub_dispatcher_connect = None
            return
        self._api_category_count[api_category] += 1

    async def async_register_api_interest(self, api_category):
        """Increment the number of entities with data needs from an API category."""
        # If this is the first registration we have, start a time interval:
        if not self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect = async_track_time_interval(
                self.hass,
                self._async_update_listener_action,
                timedelta(seconds=self._scan_interval_seconds),
            )

        self._api_category_count[api_category] += 1

        # Lock API updates in case multiple entities are trying to call the same API
        # endpoint at once:
        async with self._api_category_locks[api_category]:
            if api_category not in self.data:
                self.data[api_category] = await self._async_fetch_from_api(api_category)

    async def async_update(self):
        """Update sensor/binary sensor data."""
        tasks = {}
        for category, count in self._api_category_count.items():
            if count == 0:
                continue
            tasks[category] = self._async_fetch_from_api(category)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for api_category, result in zip(tasks, results):
            if isinstance(result, RainMachineError):
                _LOGGER.error(
                    "There was an error while updating %s: %s", api_category, result
                )
                continue
            self.data[api_category] = result

        async_dispatcher_send(self.hass, SENSOR_UPDATE_TOPIC)


class RainMachineEntity(Entity):
    """Define a generic RainMachine entity."""

    def __init__(self, rainmachine):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._device_class = None
        self._dispatcher_handlers = []
        self._name = None
        self.rainmachine = rainmachine

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.rainmachine.controller.mac)},
            "name": self.rainmachine.controller.name,
            "manufacturer": "RainMachine",
            "model": "Version {0} (API: {1})".format(
                self.rainmachine.controller.hardware_version,
                self.rainmachine.controller.api_version,
            ),
            "sw_version": self.rainmachine.controller.software_version,
        }

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        for handler in self._dispatcher_handlers:
            handler()
