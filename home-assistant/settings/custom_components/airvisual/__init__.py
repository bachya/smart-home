"""The airvisual component."""
import asyncio
from datetime import timedelta
from math import ceil

from pyairvisual import Client
from pyairvisual.errors import AirVisualError, NodeProError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_GEOGRAPHIES,
    CONF_INTEGRATION_TYPE,
    DATA_COORDINATOR,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY,
    INTEGRATION_TYPE_NODE_PRO,
    LOGGER,
)

PLATFORMS = ["air_quality", "sensor"]

DEFAULT_ATTRIBUTION = "Data provided by AirVisual"
DEFAULT_NODE_PRO_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_OPTIONS = {CONF_SHOW_ON_MAP: True}

GEOGRAPHY_COORDINATES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.latitude,
        vol.Required(CONF_LONGITUDE): cv.longitude,
    }
)

GEOGRAPHY_PLACE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STATE): cv.string,
        vol.Required(CONF_COUNTRY): cv.string,
    }
)

CLOUD_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_GEOGRAPHIES, default=[]): vol.All(
            cv.ensure_list,
            [vol.Any(GEOGRAPHY_COORDINATES_SCHEMA, GEOGRAPHY_PLACE_SCHEMA)],
        ),
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: CLOUD_API_SCHEMA}, extra=vol.ALLOW_EXTRA)


@callback
def async_get_geography_id(geography_dict):
    """Generate a unique ID from a geography dict."""
    if not geography_dict:
        return

    if CONF_CITY in geography_dict:
        return ", ".join(
            (
                geography_dict[CONF_CITY],
                geography_dict[CONF_STATE],
                geography_dict[CONF_COUNTRY],
            )
        )
    return ", ".join(
        (str(geography_dict[CONF_LATITUDE]), str(geography_dict[CONF_LONGITUDE]))
    )


@callback
def async_get_cloud_api_update_interval(hass, api_key):
    """Get a leveled scan interval for a particular cloud API key.

    This will shift based on the number of active consumers, thus keeping the user
    under the monthly API limit.
    """
    num_consumers = len(
        {
            config_entry
            for config_entry in hass.config_entries.async_entries(DOMAIN)
            if config_entry.data.get(CONF_API_KEY) == api_key
        }
    )

    # Assuming 10,000 calls per month and a "smallest possible month" of 28 days; note
    # that we give a buffer of 1500 API calls for any drift, restarts, etc.:
    minutes_between_api_calls = ceil(1 / (8500 / 28 / 24 / 60 / num_consumers))
    return timedelta(minutes=minutes_between_api_calls)


@callback
def async_reset_coordinator_update_intervals(hass, update_interval):
    """Update any existing data coordinators with a new update interval."""
    if not hass.data[DOMAIN][DATA_COORDINATOR]:
        return

    for coordinator in hass.data[DOMAIN][DATA_COORDINATOR].values():
        coordinator.update_interval = update_interval


async def async_setup(hass, config):
    """Set up the AirVisual component."""
    hass.data[DOMAIN] = {DATA_COORDINATOR: {}}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    for geography in conf.get(
        CONF_GEOGRAPHIES,
        [{CONF_LATITUDE: hass.config.latitude, CONF_LONGITUDE: hass.config.longitude}],
    ):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_API_KEY: conf[CONF_API_KEY], **geography},
            )
        )

    return True


@callback
def _standardize_geography_config_entry(hass, config_entry):
    """Ensure that geography config entries have appropriate properties."""
    entry_updates = {}

    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = config_entry.data[CONF_API_KEY]
    if not config_entry.options:
        # If the config entry doesn't already have any options set, set defaults:
        entry_updates["options"] = {CONF_SHOW_ON_MAP: True}
    if CONF_INTEGRATION_TYPE not in config_entry.data:
        # If the config entry data doesn't contain the integration type, add it:
        entry_updates["data"] = {
            **config_entry.data,
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY,
        }

    if not entry_updates:
        return

    hass.config_entries.async_update_entry(config_entry, **entry_updates)


@callback
def _standardize_node_pro_config_entry(hass, config_entry):
    """Ensure that Node/Pro config entries have appropriate properties."""
    entry_updates = {}

    if CONF_INTEGRATION_TYPE not in config_entry.data:
        # If the config entry data doesn't contain the integration type, add it:
        entry_updates["data"] = {
            **config_entry.data,
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_NODE_PRO,
        }

    if not entry_updates:
        return

    hass.config_entries.async_update_entry(config_entry, **entry_updates)


async def async_setup_entry(hass, config_entry):
    """Set up AirVisual as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)

    if CONF_API_KEY in config_entry.data:
        _standardize_geography_config_entry(hass, config_entry)

        client = Client(api_key=config_entry.data[CONF_API_KEY], session=websession)

        update_interval = async_get_cloud_api_update_interval(
            hass, config_entry.data[CONF_API_KEY]
        )

        async def async_update_data():
            """Get new data from the API."""
            if CONF_CITY in config_entry.data:
                api_coro = client.api.city(
                    config_entry.data[CONF_CITY],
                    config_entry.data[CONF_STATE],
                    config_entry.data[CONF_COUNTRY],
                )
            else:
                api_coro = client.api.nearest_city(
                    config_entry.data[CONF_LATITUDE], config_entry.data[CONF_LONGITUDE],
                )

            try:
                return await api_coro
            except AirVisualError as err:
                raise UpdateFailed(f"Error while retrieving data: {err}")

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name="geography data",
            update_interval=update_interval,
            update_method=async_update_data,
        )

        # Ensure any other, existing config entries that use this API key are updated
        # with the new scan interval:
        async_reset_coordinator_update_intervals(hass, update_interval)

        # Only geography-based entries have options:
        config_entry.add_update_listener(async_update_options)
    else:
        _standardize_node_pro_config_entry(hass, config_entry)

        client = Client(session=websession)

        async def async_update_data():
            """Get new data from the API."""
            try:
                return await client.node.from_samba(
                    config_entry.data[CONF_IP_ADDRESS],
                    config_entry.data[CONF_PASSWORD],
                    include_history=False,
                    include_trends=False,
                )
            except NodeProError as err:
                raise UpdateFailed(f"Error while retrieving data: {err}")

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name="Node/Pro data",
            update_interval=DEFAULT_NODE_PRO_SCAN_INTERVAL,
            update_method=async_update_data,
        )

    await coordinator.async_refresh()

    hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: One geography per config entry
    if version == 1:
        version = config_entry.version = 2

        # Update the config entry to only include the first geography (there is always
        # guaranteed to be at least one):
        geographies = list(config_entry.data[CONF_GEOGRAPHIES])
        first_geography = geographies.pop(0)
        first_id = async_get_geography_id(first_geography)

        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=first_id,
            title=f"Cloud API ({first_id})",
            data={CONF_API_KEY: config_entry.data[CONF_API_KEY], **first_geography},
        )

        # For any geographies that remain, create a new config entry for each one:
        for geography in geographies:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={CONF_API_KEY: config_entry.data[CONF_API_KEY], **geography},
                )
            )

    LOGGER.info("Migration to version %s successful", version)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an AirVisual config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(config_entry.entry_id)

    return unload_ok


async def async_update_options(hass, config_entry):
    """Handle an options update."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id]
    await coordinator.async_request_refresh()


class AirVisualEntity(Entity):
    """Define a generic AirVisual entity."""

    def __init__(self, coordinator):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = None
        self._unit = None
        self.coordinator = coordinator

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(self.coordinator.async_add_listener(update))

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self):
        """Update the entity from the latest data."""
        raise NotImplementedError
