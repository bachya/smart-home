"""Provides data for trash/recycling/etc. pickups."""
from logging import getLogger
from datetime import timedelta
from math import ceil

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.dt import now
from homeassistant.util.json import load_json, save_json

_LOGGER = getLogger(__name__)

ATTR_PICKUP_DATE = 'pickup_date'

CONF_RECOLLECT_PLACE_ID = 'recollect_place_id'

DEFAULT_ATTR = 'City and County of Denver, CO'

CONFIG_FILE = '.recollect_place_id'
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
PICKUP_TYPES = {
    'compost': ('Compost Pickup', 'mdi:food-apple'),
    'extra_trash': ('Extra Trash Pickup', 'mdi:truck'),
    'recycling': ('Recycling Pickup', 'mdi:recycle'),
    'trash': ('Trash Pickup', 'mdi:delete')
}

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_API_KEY, CONF_MONITORED_CONDITIONS),
    PLATFORM_SCHEMA.extend({
        vol.Exclusive(CONF_API_KEY, 'method'): cv.string,
        vol.Exclusive(CONF_RECOLLECT_PLACE_ID, 'method'): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=list(PICKUP_TYPES)):
            vol.All(cv.ensure_list, [vol.In(PICKUP_TYPES)]),
    }))


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Configure the platform and add the sensors."""
    from pyden import Client
    from pyden.errors import PydenError

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(websession)

    conf = await hass.async_add_job(load_json, hass.config.path(CONFIG_FILE))
    place_id = conf.get(CONF_RECOLLECT_PLACE_ID)

    if place_id:
        client.trash.place_id = place_id
    elif config.get(CONF_RECOLLECT_PLACE_ID):
        client.trash.place_id = config[CONF_RECOLLECT_PLACE_ID]
    elif config.get(CONF_API_KEY):
        try:
            await client.trash.init_from_coords(
                hass.config.latitude, hass.config.longitude,
                config[CONF_API_KEY])
        except PydenError as err:
            _LOGGER.error("Couldn't initialize from API key: %s", err)
            return

    if client.trash.place_id != place_id:
        config_data = {CONF_RECOLLECT_PLACE_ID: client.trash.place_id}
        await hass.async_add_job(
            save_json, hass.config.path(CONFIG_FILE), config_data)

    sensors = []
    for pickup_type in config[CONF_MONITORED_CONDITIONS]:
        name, icon = PICKUP_TYPES[pickup_type]
        data = PickupData(client, pickup_type, hass.config.time_zone)
        sensors.append(DenverTrashSensor(data, name, icon))

    async_add_devices(sensors, True)


class DenverTrashSensor(Entity):
    """Define a class representation of the sensor."""

    def __init__(self, data, name, icon):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTR}
        self._data = data
        self._icon = icon
        self._name = name
        self._state = None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon of the pickup type."""
        return self._icon

    @property
    def name(self):
        """Return the name of the pickup type."""
        return self._name

    @property
    def state(self):
        """Return the next pickup date of the pickup type."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update the status."""
        _LOGGER.debug('Updating sensor: %s', self._name)

        await self._data.async_update()
        self._state = self._data.humanized_pickup
        self._attrs.update({ATTR_PICKUP_DATE: self._data.raw_date})


class PickupData:  # pylint: disable=too-few-public-methods
    """Define a class to deal with representations of the pickup data."""

    def __init__(self, client, pickup_type, local_tz):
        """Initialize."""
        self._client = client
        self._local_tz = local_tz
        self._pickup_type = pickup_type
        self.humanized_pickup = None
        self.raw_date = None

    def _humanize_pickup(self, future_date):
        """Humanize how many pickups away this type is."""
        today = now(self._local_tz).date()
        delta_days = (future_date - today).days

        if delta_days < 1:
            return "in today's pickup"

        if delta_days < 2:
            return "in tomorrow's pickup"

        if delta_days <= 7:
            return 'in the next pickup'

        return 'in {0} pickups'.format(ceil(delta_days / 7))

    async def async_update(self):
        """Update the data for the pickup."""
        from pyden.errors import PydenError

        try:
            data = await self._client.trash.next_pickup(
                self._client.trash.PickupTypes[self._pickup_type])
            next_date = data.date()
            self.humanized_pickup = self._humanize_pickup(next_date)
            self.raw_date = next_date.strftime('%B %e, %Y')
        except PydenError as err:
            _LOGGER.error(
                'Unable to get date for %s: %s', self._pickup_type, err)
