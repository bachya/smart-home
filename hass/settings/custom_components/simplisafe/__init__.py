"""Support for SimpliSafe alarm systems."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Callable, cast
from uuid import UUID

from simplipy import get_api
from simplipy.api import API
from simplipy.errors import (
    EndpointUnavailableError,
    InvalidCredentialsError,
    SimplipyError,
)
from simplipy.sensor.v2 import SensorV2
from simplipy.sensor.v3 import SensorV3
from simplipy.system import SystemNotification
from simplipy.system.v2 import SystemV2
from simplipy.system.v3 import SystemV3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.service import (
    async_register_admin_service,
    verify_domain_control,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_ALARM_DURATION,
    ATTR_ALARM_VOLUME,
    ATTR_CHIME_VOLUME,
    ATTR_ENTRY_DELAY_AWAY,
    ATTR_ENTRY_DELAY_HOME,
    ATTR_EXIT_DELAY_AWAY,
    ATTR_EXIT_DELAY_HOME,
    ATTR_LIGHT,
    ATTR_VOICE_PROMPT_VOLUME,
    DATA_CLIENT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    VOLUMES,
)

EVENT_SIMPLISAFE_NOTIFICATION = "SIMPLISAFE_NOTIFICATION"

DEFAULT_SOCKET_MIN_RETRY = 15

PLATFORMS = (
    "alarm_control_panel",
    "binary_sensor",
    "lock",
    "sensor",
)

ATTR_CATEGORY = "category"
ATTR_MESSAGE = "message"
ATTR_PIN_LABEL = "label"
ATTR_PIN_LABEL_OR_VALUE = "label_or_pin"
ATTR_PIN_VALUE = "pin"
ATTR_SYSTEM_ID = "system_id"
ATTR_TIMESTAMP = "timestamp"

SERVICE_BASE_SCHEMA = vol.Schema({vol.Required(ATTR_SYSTEM_ID): cv.positive_int})

SERVICE_REMOVE_PIN_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {vol.Required(ATTR_PIN_LABEL_OR_VALUE): cv.string}
)

SERVICE_SET_PIN_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {vol.Required(ATTR_PIN_LABEL): cv.string, vol.Required(ATTR_PIN_VALUE): cv.string}
)

SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_ALARM_DURATION): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=30, max=480),
        ),
        vol.Optional(ATTR_ALARM_VOLUME): vol.All(vol.Coerce(int), vol.In(VOLUMES)),
        vol.Optional(ATTR_CHIME_VOLUME): vol.All(vol.Coerce(int), vol.In(VOLUMES)),
        vol.Optional(ATTR_ENTRY_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=30, max=255),
        ),
        vol.Optional(ATTR_ENTRY_DELAY_HOME): vol.All(
            cv.time_period, lambda value: value.total_seconds(), vol.Range(max=255)
        ),
        vol.Optional(ATTR_EXIT_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=45, max=255),
        ),
        vol.Optional(ATTR_EXIT_DELAY_HOME): vol.All(
            cv.time_period, lambda value: value.total_seconds(), vol.Range(max=255)
        ),
        vol.Optional(ATTR_LIGHT): cv.boolean,
        vol.Optional(ATTR_VOICE_PROMPT_VOLUME): vol.All(
            vol.Coerce(int), vol.In(VOLUMES)
        ),
    }
)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


async def async_get_client_id(hass: HomeAssistant) -> str:
    """Get a client ID (based on the HASS unique ID) for the SimpliSafe API.

    Note that SimpliSafe requires full, "dashed" versions of UUIDs.
    """
    hass_id = await hass.helpers.instance_id.async_get()
    return str(UUID(hass_id))


async def async_register_base_station(
    hass: HomeAssistant, system: SystemV2 | SystemV3, config_entry_id: str
) -> None:
    """Register a new bridge."""
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, system.serial)},
        manufacturer="SimpliSafe",
        model=system.version,
        name=system.address,
    )


@callback
def _async_standardize_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Bring a config entry up to current standards."""
    if CONF_PASSWORD not in config_entry.data:
        raise ConfigEntryAuthFailed("Config schema change requires re-authentication")

    entry_updates = {}
    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = config_entry.data[CONF_USERNAME]
    if CONF_CODE in config_entry.data:
        # If an alarm code was provided as part of configuration.yaml, pop it out of
        # the config entry's data and move it to options:
        data = {**config_entry.data}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **config_entry.options,
            CONF_CODE: data.pop(CONF_CODE),
        }
    if entry_updates:
        hass.config_entries.async_update_entry(config_entry, **entry_updates)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up SimpliSafe as config entry."""
    hass.data.setdefault(DOMAIN, {DATA_CLIENT: {}})
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = []

    _async_standardize_config_entry(hass, config_entry)

    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    client_id = await async_get_client_id(hass)
    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        api = await get_api(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            client_id=client_id,
            session=websession,
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed from err
    except SimplipyError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    simplisafe = SimpliSafe(hass, config_entry, api)

    try:
        await simplisafe.async_init()
    except SimplipyError as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = simplisafe
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    @callback
    def verify_system_exists(
        coro: Callable[..., Awaitable]
    ) -> Callable[..., Awaitable]:
        """Log an error if a service call uses an invalid system ID."""

        async def decorator(call: ServiceCall) -> None:
            """Decorate."""
            system_id = int(call.data[ATTR_SYSTEM_ID])
            if system_id not in simplisafe.systems:
                LOGGER.error("Unknown system ID in service call: %s", system_id)
                return
            await coro(call)

        return decorator

    @callback
    def v3_only(coro: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        """Log an error if the decorated coroutine is called with a v2 system."""

        async def decorator(call: ServiceCall) -> None:
            """Decorate."""
            system = simplisafe.systems[int(call.data[ATTR_SYSTEM_ID])]
            if system.version != 3:
                LOGGER.error("Service only available on V3 systems")
                return
            await coro(call)

        return decorator

    @verify_system_exists
    @_verify_domain_control
    async def clear_notifications(call: ServiceCall) -> None:
        """Clear all active notifications."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.clear_notifications()
        except SimplipyError as err:
            LOGGER.error("Error during service call: %s", err)

    @verify_system_exists
    @_verify_domain_control
    async def remove_pin(call: ServiceCall) -> None:
        """Remove a PIN."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.remove_pin(call.data[ATTR_PIN_LABEL_OR_VALUE])
        except SimplipyError as err:
            LOGGER.error("Error during service call: %s", err)

    @verify_system_exists
    @_verify_domain_control
    async def set_pin(call: ServiceCall) -> None:
        """Set a PIN."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.set_pin(call.data[ATTR_PIN_LABEL], call.data[ATTR_PIN_VALUE])
        except SimplipyError as err:
            LOGGER.error("Error during service call: %s", err)

    @verify_system_exists
    @v3_only
    @_verify_domain_control
    async def set_system_properties(call: ServiceCall) -> None:
        """Set one or more system parameters."""
        system = cast(SystemV3, simplisafe.systems[call.data[ATTR_SYSTEM_ID]])
        try:
            await system.set_properties(
                {
                    prop: value
                    for prop, value in call.data.items()
                    if prop != ATTR_SYSTEM_ID
                }
            )
        except SimplipyError as err:
            LOGGER.error("Error during service call: %s", err)

    for service, method, schema in (
        ("clear_notifications", clear_notifications, None),
        ("remove_pin", remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        ("set_pin", set_pin, SERVICE_SET_PIN_SCHEMA),
        (
            "set_system_properties",
            set_system_properties,
            SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA,
        ),
    ):
        async_register_admin_service(hass, DOMAIN, service, method, schema=schema)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SimpliSafe config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class SimpliSafe:
    """Define a SimpliSafe data object."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: API
    ) -> None:
        """Initialize."""
        self._api = api
        self._hass = hass
        self._system_notifications: dict[int, set[SystemNotification]] = {}
        self.config_entry = config_entry
        self.coordinator: DataUpdateCoordinator | None = None
        self.systems: dict[int, SystemV2 | SystemV3] = {}

    @callback
    def _async_process_new_notifications(self, system: SystemV2 | SystemV3) -> None:
        """Act on any new system notifications."""
        if self._hass.state != CoreState.running:
            # If HASS isn't fully running yet, it may cause the SIMPLISAFE_NOTIFICATION
            # event to fire before dependent components (like automation) are fully
            # ready. If that's the case, skip:
            return

        latest_notifications = set(system.notifications)

        to_add = latest_notifications.difference(
            self._system_notifications[system.system_id]
        )

        if not to_add:
            return

        LOGGER.debug("New system notifications: %s", to_add)

        for notification in to_add:
            text = notification.text
            if notification.link:
                text = f"{text} For more information: {notification.link}"

            self._hass.bus.async_fire(
                EVENT_SIMPLISAFE_NOTIFICATION,
                event_data={
                    ATTR_CATEGORY: notification.category,
                    ATTR_CODE: notification.code,
                    ATTR_MESSAGE: text,
                    ATTR_TIMESTAMP: notification.timestamp,
                },
            )

        self._system_notifications[system.system_id] = latest_notifications

    async def async_init(self) -> None:
        """Initialize the data class."""
        self.systems = await self._api.get_systems()
        for system in self.systems.values():
            self._system_notifications[system.system_id] = set()

            self._hass.async_create_task(
                async_register_base_station(
                    self._hass, system, self.config_entry.entry_id
                )
            )

        self.coordinator = DataUpdateCoordinator(
            self._hass,
            LOGGER,
            name=self.config_entry.data[CONF_USERNAME],
            update_interval=DEFAULT_SCAN_INTERVAL,
            update_method=self.async_update,
        )

    async def async_update(self) -> None:
        """Get updated data from SimpliSafe."""

        async def async_update_system(system: SystemV2 | SystemV3) -> None:
            """Update a system."""
            await system.update(cached=system.version != 3)
            self._async_process_new_notifications(system)

        tasks = [async_update_system(system) for system in self.systems.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, InvalidCredentialsError):
                raise ConfigEntryAuthFailed("Invalid credentials") from result

            if isinstance(result, EndpointUnavailableError):
                # In case the user attempts an action not allowed in their current plan,
                # we merely log that message at INFO level (so the user is aware,
                # but not spammed with ERROR messages that they cannot change):
                LOGGER.info(result)

            if isinstance(result, SimplipyError):
                raise UpdateFailed(f"SimpliSafe error while updating: {result}")


class SimpliSafeEntity(CoordinatorEntity):
    """Define a base SimpliSafe entity."""

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemV2 | SystemV3,
        name: str,
        *,
        serial: str | None = None,
    ) -> None:
        """Initialize."""
        assert simplisafe.coordinator
        super().__init__(simplisafe.coordinator)

        if serial:
            self._serial = serial
        else:
            self._serial = system.serial

        self._attr_extra_state_attributes = {ATTR_SYSTEM_ID: system.system_id}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, system.system_id)},
            "manufacturer": "SimpliSafe",
            "model": str(system.version),
            "name": name,
            "via_device": (DOMAIN, system.serial),
        }
        self._attr_name = f"{system.address} {name}"
        self._attr_unique_id = self._serial
        self._online = True
        self._simplisafe = simplisafe
        self._system = system

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        # We can easily detect if the V3 system is offline, but no simple check exists
        # for the V2 system. Therefore, assuming the coordinator hasn't failed, we mark
        # the entity as available if:
        #   1. We can verify that the system is online (assuming True if we can't)
        #   2. We can verify that the entity is online
        if isinstance(self._system, SystemV3):
            system_offline = self._system.offline
        else:
            system_offline = False

        return super().available and self._online and not system_offline

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the entity with new REST API data."""
        self.async_update_from_rest_api()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_update_from_rest_api()

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        raise NotImplementedError()


class SimpliSafeBaseSensor(SimpliSafeEntity):
    """Define a SimpliSafe base (binary) sensor."""

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemV2 | SystemV3,
        sensor: SensorV2 | SensorV3,
    ) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, sensor.name, serial=sensor.serial)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, sensor.serial)},
            "manufacturer": "SimpliSafe",
            "model": sensor.type.name,
            "name": sensor.name,
            "via_device": (DOMAIN, system.serial),
        }

        human_friendly_name = " ".join([w.title() for w in sensor.type.name.split("_")])
        self._attr_name = f"{super().name} {human_friendly_name}"

        self._sensor = sensor
