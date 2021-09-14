"""Support for SimpliSafe locks."""
from __future__ import annotations

from typing import Any

from simplipy.errors import SimplipyError
from simplipy.lock import Lock, LockStates
from simplipy.system.v3 import SystemV3

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafe, SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN, LOGGER

ATTR_LOCK_LOW_BATTERY = "lock_low_battery"
ATTR_PIN_PAD_LOW_BATTERY = "pin_pad_low_battery"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe locks based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    locks = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping lock setup for V2 system: %s", system.system_id)
            continue

        for lock in system.locks.values():
            locks.append(SimpliSafeLock(simplisafe, system, lock))

    async_add_entities(locks)


class SimpliSafeLock(SimpliSafeEntity, LockEntity):
    """Define a SimpliSafe lock."""

    def __init__(self, simplisafe: SimpliSafe, system: SystemV3, lock: Lock) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, lock.name, serial=lock.serial)

        self._lock = lock

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        try:
            await self._lock.lock()
        except SimplipyError as err:
            LOGGER.error('Error while locking "%s": %s', self._lock.name, err)
            return

        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        try:
            await self._lock.unlock()
        except SimplipyError as err:
            LOGGER.error('Error while unlocking "%s": %s', self._lock.name, err)
            return

        self._attr_is_locked = False
        self.async_write_ha_state()

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_extra_state_attributes.update(
            {
                ATTR_LOCK_LOW_BATTERY: self._lock.lock_low_battery,
                ATTR_PIN_PAD_LOW_BATTERY: self._lock.pin_pad_low_battery,
            }
        )

        self._attr_is_jammed = self._lock.state == LockStates.jammed
        self._attr_is_locked = self._lock.state == LockStates.locked
