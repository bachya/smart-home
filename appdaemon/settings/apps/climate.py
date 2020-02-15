"""Define automations for climate control."""
from threading import Lock
from typing import Union

import voluptuous as vol
from const import EVENT_PRESENCE_CHANGE, EVENT_PROXIMITY_CHANGE
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_AQI_SENSOR = "aqi"
CONF_AQI_THRESHOLD = "aqi_threshold"
CONF_AWAY_MODE = "away_mode"
CONF_BRIGHTNESS_PERCENT_SENSOR = "sensor.outdoor_brightness_percent_sensor"
CONF_BRIGHTNESS_SENSOR = "sensor.outdoor_brightness_sensor"
CONF_DISTANCE = "distance"
CONF_ECO_HIGH_THRESHOLD = "eco_high_threshold"
CONF_ECO_LOW_THRESHOLD = "eco_low_threshold"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_INDOOR_TEMPERATURE_SENSOR = "indoor_temperature_sensor"
CONF_LAST_HVAC_MODE = "last_hvac_mode"
CONF_LIGHTNING_WINDOW = "notification_window_seconds"
CONF_OUTDOOR_BRIGHTNESS_PERCENT_SENSOR = "outdoor_brightness_percent_sensor"
CONF_OUTDOOR_BRIGHTNESS_SENSOR = "outdoor_brightness_sensor"
CONF_OUTDOOR_HIGH_THRESHOLD = "outdoor_high_threshold"
CONF_OUTDOOR_LOW_THRESHOLD = "outdoor_low_threshold"
CONF_OUTDOOR_TEMPERATURE_SENSOR = "outdoor_temperature_sensor"
CONF_THERMOSTAT = "thermostat"

FAN_MODE_AUTO_LOW = "Auto Low"
FAN_MODE_CIRCULATE = "Circulate"
FAN_MODE_ON_LOW = "On Low"

HVAC_MODE_AUTO = "heat_cool"
HVAC_MODE_COOL = "cool"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_OFF = "off"

HANDLE_ECO_MODE = "eco_mode"

EVENT_LIGHTNING_DETECTED = "LIGHTNING_DETECTED"


class AdjustOnProximity(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to adjust climate based on proximity to home."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_arrive_home,
            EVENT_PRESENCE_CHANGE,
            new=self.presence_manager.HomeStates.just_arrived.value,
            first=True,
        )

        self.listen_event(self._on_proximity_change, EVENT_PROXIMITY_CHANGE)

    def _on_arrive_home(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Last ditch: turn the thermostat to home when someone arrives."""
        if self.climate_manager.away_mode:
            self.log('Last ditch: setting thermostat to "Home" (arrived)')
            self.climate_manager.set_home()

    def _on_proximity_change(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "PROXIMITY_CHANGE" events."""
        if self.climate_manager.outdoor_temperature_extreme:
            # Scenario 1: Anything -> Away (Extreme Temps)
            if data["new"] == self.presence_manager.ProximityZones.away.value:
                self.climate_manager.set_away()

            # Scenario 2: Away -> Anything (Extreme Temps)
            elif data["old"] == self.presence_manager.ProximityZones.away.value:
                self.climate_manager.set_home()
        else:
            # Scenario 3: Home -> Anything
            if data["old"] == self.presence_manager.ProximityZones.home.value:
                self.climate_manager.set_away()

            # Scenario 4: Anything -> Nearby
            elif data["new"] == self.presence_manager.ProximityZones.nearby.value:
                self.climate_manager.set_home()


class ClimateManager(Base):  # pylint: disable=too-many-public-methods
    """Define an app to represent climate control."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_AWAY_MODE): cv.entity_id,
            vol.Required(CONF_ECO_HIGH_THRESHOLD): cv.entity_id,
            vol.Required(CONF_ECO_LOW_THRESHOLD): cv.entity_id,
            vol.Required(CONF_HUMIDITY_SENSOR): cv.entity_id,
            vol.Required(CONF_INDOOR_TEMPERATURE_SENSOR): cv.entity_id,
            vol.Required(CONF_OUTDOOR_BRIGHTNESS_PERCENT_SENSOR): cv.entity_id,
            vol.Required(CONF_OUTDOOR_BRIGHTNESS_SENSOR): cv.entity_id,
            vol.Required(CONF_OUTDOOR_HIGH_THRESHOLD): cv.entity_id,
            vol.Required(CONF_OUTDOOR_LOW_THRESHOLD): cv.entity_id,
            vol.Required(CONF_OUTDOOR_TEMPERATURE_SENSOR): cv.entity_id,
            vol.Required(CONF_THERMOSTAT): cv.entity_id,
        }
    )

    def configure(self) -> None:
        """Configure."""
        if self.away_mode:
            self._set_away()

        self.listen_state(self._on_away_mode_change, self.args[CONF_AWAY_MODE])

    @property
    def away_mode(self) -> bool:
        """Return the state of away mode."""
        return self.get_state(self.args[CONF_AWAY_MODE]) == "on"

    @property
    def eco_high_temperature(self) -> float:
        """Return the upper limit of eco mode."""
        return float(self.get_state(self.args[CONF_ECO_HIGH_THRESHOLD]))

    @eco_high_temperature.setter
    def eco_high_temperature(self, value: int) -> None:
        """Set the upper limit of eco mode."""
        self.set_value(self.args[CONF_ECO_HIGH_THRESHOLD], value)

    @property
    def eco_low_temperature(self) -> float:
        """Return the lower limit of eco mode."""
        return float(self.get_state(self.args[CONF_ECO_LOW_THRESHOLD]))

    @eco_low_temperature.setter
    def eco_low_temperature(self, value: int) -> None:
        """Set the upper limit of eco mode."""
        self.set_value(self.args[CONF_ECO_LOW_THRESHOLD], value)

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return self.get_state(self.args[CONF_THERMOSTAT], attribute="fan_mode")

    @property
    def indoor_humidity(self) -> float:
        """Return the average indoor humidity."""
        return float(self.get_state(self.args[CONF_HUMIDITY_SENSOR]))

    @property
    def indoor_temperature(self) -> float:
        """Return the average indoor temperature."""
        return float(self.get_state(self.args[CONF_INDOOR_TEMPERATURE_SENSOR]))

    @property
    def hvac_mode(self) -> str:
        """Return the current operating mode."""
        return self.get_state(self.args[CONF_THERMOSTAT])

    @property
    def outdoor_brightness(self) -> float:
        """Return the outdoor brightness in lux."""
        return float(self.get_state(self.args[CONF_BRIGHTNESS_SENSOR]))

    @property
    def outdoor_brightness_percentage(self) -> float:
        """Return the human-perception of brightness percentage."""
        return float(self.get_state(self.args[CONF_BRIGHTNESS_PERCENT_SENSOR]))

    @property
    def outdoor_high_temperature(self) -> float:
        """Return the upper limit of "extreme" outdoor temperatures."""
        return float(self.get_state(self.args[CONF_OUTDOOR_HIGH_THRESHOLD]))

    @property
    def outdoor_low_temperature(self) -> float:
        """Return the lower limit of "extreme" outdoor temperatures."""
        return float(self.get_state(self.args[CONF_OUTDOOR_LOW_THRESHOLD]))

    @property
    def outdoor_temperature(self) -> float:
        """Return the outdoor temperature."""
        return float(self.get_state(self.args[CONF_OUTDOOR_TEMPERATURE_SENSOR]))

    @property
    def outdoor_temperature_extreme(self) -> float:
        """Return whether the outside temperature is at extreme limits."""
        return (
            self.outdoor_temperature < self.outdoor_low_temperature
            or self.outdoor_temperature > self.outdoor_high_temperature
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature the thermostat is currently set to."""
        try:
            return float(
                self.get_state(self.args[CONF_THERMOSTAT], attribute="temperature")
            )
        except TypeError:
            return 0.0

    def _on_away_mode_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """React when away mode is toggled."""
        if new == "on":
            self._set_away()
        else:
            self._set_home()

    def _on_eco_temp_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """React when the temperature goes above or below its eco thresholds."""
        current_temperature = float(new)

        if (
            current_temperature > self.eco_high_temperature
            and self.hvac_mode != HVAC_MODE_COOL
        ):
            self.log('Eco Mode: setting to "Cool" (%s°)', self.eco_high_temperature)
            self.set_mode_cool()
            self.set_temperature(self.eco_high_temperature)
        elif (
            current_temperature < self.eco_low_temperature
            and self.hvac_mode != HVAC_MODE_HEAT
        ):
            self.log('Eco Mode: setting to "Heat" (%s°)', self.eco_low_temperature)
            self.set_mode_heat()
            self.set_temperature(self.eco_low_temperature)
        elif (
            self.eco_low_temperature <= current_temperature <= self.eco_high_temperature
            and self.hvac_mode != HVAC_MODE_OFF
        ):
            self.log('Within eco mode limits; turning thermostat to "Off"')
            self.set_mode_off()

    def _restore_previous_state(self) -> None:
        """Restore the thermostat to its previous state."""
        self._set_hvac_mode(self.get_state(CONF_LAST_HVAC_MODE))

    def _set_away(self) -> None:
        """Put the thermostat in "Away" mode."""
        self.log('Setting thermostat to "Away" mode')

        self.set_mode_off()

        self.data[HANDLE_ECO_MODE] = self.listen_state(
            self._on_eco_temp_change, self.args[CONF_INDOOR_TEMPERATURE_SENSOR]
        )

    def _set_fan_mode(self, fan_mode: str) -> None:
        """Set the themostat's fan mode."""
        if fan_mode == self.fan_mode:
            return

        self.log('Setting fan mode to "%s"', fan_mode.title())
        self.call_service(
            "climate/set_fan_mode",
            entity_id=self.args[CONF_THERMOSTAT],
            fan_mode=fan_mode,
        )

    def _set_home(self) -> None:
        """Put the thermostat in "Home" mode."""
        self.log('Setting thermostat to "Home" mode')

        handle = self.data.pop(HANDLE_ECO_MODE)
        self.cancel_listen_state(handle)

        # If the thermostat isn't doing anything, set it to the previous settings
        # (before away mode); otherwise, let it keep doing its thing:
        if self.hvac_mode == HVAC_MODE_OFF:
            self._restore_previous_state()

    def _set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the themostat's operation mode."""
        if hvac_mode == self.hvac_mode:
            return

        # Set the previous HVAC mode in case we want to return to it:
        self.select_option(CONF_LAST_HVAC_MODE, self.hvac_mode)

        self.log('Setting operation mode to "%s"', hvac_mode.title())
        self.call_service(
            "climate/set_hvac_mode",
            entity_id=self.args[CONF_THERMOSTAT],
            hvac_mode=hvac_mode,
        )

    def bump_temperature(self, value: int) -> None:
        """Bump the current temperature."""
        if HVAC_MODE_COOL in (self.hvac_mode, self._last_hvac_mode):
            value *= -1
        self.set_temperature(self.target_temperature + value)

    def set_away(self) -> None:
        """Set the thermostat to away."""
        self.turn_on(self.args[CONF_AWAY_MODE])

    def set_fan_auto_low(self) -> None:
        """Set the fan mode to auto_low."""
        self._set_fan_mode(FAN_MODE_AUTO_LOW)

    def set_fan_circulate(self) -> None:
        """Set the fan mode to circulate."""
        self._set_fan_mode(FAN_MODE_CIRCULATE)

    def set_fan_on_low(self) -> None:
        """Set the fan mode to on_low."""
        self._set_fan_mode(FAN_MODE_ON_LOW)

    def set_home(self) -> None:
        """Set the thermostat to home."""
        self.turn_off(self.args[CONF_AWAY_MODE])

    def set_mode_auto(self) -> None:
        """Set the operation mode to auto."""
        self._set_hvac_mode(HVAC_MODE_AUTO)

    def set_mode_cool(self) -> None:
        """Set the operation mode to cool."""
        self._set_hvac_mode(HVAC_MODE_COOL)

    def set_mode_heat(self) -> None:
        """Set the operation mode to heat."""
        self._set_hvac_mode(HVAC_MODE_HEAT)

    def set_mode_off(self) -> None:
        """Set the operation mode to off."""
        self._set_hvac_mode(HVAC_MODE_OFF)

    def set_temperature(self, temperature: float) -> None:
        """Set the thermostat temperature."""
        if temperature == self.target_temperature:
            return

        self.call_service(
            "climate/set_temperature",
            entity_id=self.args[CONF_THERMOSTAT],
            temperature=str(int(temperature)),
        )

    def toggle(self) -> None:
        """Toggle the thermostat between off and its previous HVAC state/temp."""
        if self.hvac_mode == HVAC_MODE_OFF:
            self._restore_previous_state()
        else:
            self.set_mode_off()


class LightningDetected(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify when lightning is detected."""

    def configure(self) -> None:
        """Configure."""
        self._active = False
        self._lock = Lock()

        self.listen_event(self._on_lightning_detected, EVENT_LIGHTNING_DETECTED)

    def _on_lightning_detected(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "LIGHTNING_DETECTED" events."""
        with self._lock:
            if self._active:
                return

            send_notification(
                self,
                "presence:home",
                f"Lightning detected {data[CONF_DISTANCE]} miles away.",
                title="Lightning Detected ⚡️",
            )

            self._active = True
            self.run_in(self._on_reset, self.args[CONF_LIGHTNING_WINDOW])

    def _on_reset(self, kwargs: dict) -> None:
        """Reset the notification window."""
        self._active = False
