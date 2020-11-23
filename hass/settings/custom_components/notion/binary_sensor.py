"""Support for Notion binary sensors."""
from typing import Callable

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from . import NotionEntity
from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    SENSOR_BATTERY,
    SENSOR_DOOR,
    SENSOR_GARAGE_DOOR,
    SENSOR_LEAK,
    SENSOR_MISSING,
    SENSOR_SAFE,
    SENSOR_SLIDING,
    SENSOR_SMOKE_CO,
    SENSOR_WINDOW_HINGED_HORIZONTAL,
    SENSOR_WINDOW_HINGED_VERTICAL,
)

BINARY_SENSOR_TYPES = {
    SENSOR_BATTERY: ("Low Battery", "battery"),
    SENSOR_DOOR: ("Door", DEVICE_CLASS_DOOR),
    SENSOR_GARAGE_DOOR: ("Garage Door", "garage_door"),
    SENSOR_LEAK: ("Leak Detector", DEVICE_CLASS_MOISTURE),
    SENSOR_MISSING: ("Missing", DEVICE_CLASS_CONNECTIVITY),
    SENSOR_SAFE: ("Safe", DEVICE_CLASS_DOOR),
    SENSOR_SLIDING: ("Sliding Door/Window", DEVICE_CLASS_DOOR),
    SENSOR_SMOKE_CO: ("Smoke/Carbon Monoxide Detector", DEVICE_CLASS_SMOKE),
    SENSOR_WINDOW_HINGED_HORIZONTAL: ("Hinged Window", DEVICE_CLASS_WINDOW),
    SENSOR_WINDOW_HINGED_VERTICAL: ("Hinged Window", DEVICE_CLASS_WINDOW),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    """Set up Notion sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

    sensor_list = []
    for task_id, task in coordinator.data["tasks"].items():
        if task["task_type"] not in BINARY_SENSOR_TYPES:
            continue

        name, device_class = BINARY_SENSOR_TYPES[task["task_type"]]
        sensor = coordinator.data["sensors"][task["sensor_id"]]

        sensor_list.append(
            NotionBinarySensor(
                coordinator,
                task_id,
                sensor["id"],
                sensor["bridge"]["id"],
                sensor["system_id"],
                name,
                device_class,
            )
        )

    async_add_entities(sensor_list)


class NotionBinarySensor(NotionEntity, BinarySensorEntity):
    """Define a Notion sensor."""

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Fetch new state data for the sensor."""
        task = self.coordinator.data["tasks"][self._task_id]

        if "value" in task["status"]:
            self._state = task["status"]["value"]
        elif task["task_type"] == SENSOR_BATTERY:
            self._state = task["status"]["data"]["to_state"]

    @property
    def is_on(self) -> bool:
        """Return whether the sensor is on or off."""
        task = self.coordinator.data["tasks"][self._task_id]

        if task["task_type"] == SENSOR_BATTERY:
            return self._state == "critical"
        if task["task_type"] in (
            SENSOR_DOOR,
            SENSOR_GARAGE_DOOR,
            SENSOR_SAFE,
            SENSOR_SLIDING,
            SENSOR_WINDOW_HINGED_HORIZONTAL,
            SENSOR_WINDOW_HINGED_VERTICAL,
        ):
            return self._state != "closed"
        if task["task_type"] == SENSOR_LEAK:
            return self._state != "no_leak"
        if task["task_type"] == SENSOR_MISSING:
            return self._state == "not_missing"
        if task["task_type"] == SENSOR_SMOKE_CO:
            return self._state != "no_alarm"
