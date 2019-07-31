"""Define automations for climate control."""
from threading import Lock
from typing import Callable, Optional, Union
import voluptuous as vol

from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification
from const import (
    CONF_ENTITY_IDS,
    CONF_PROPERTIES,
    EVENT_PRESENCE_CHANGE,
    EVENT_PROXIMITY_CHANGE,
)

CONF_THERMOSTAT = "thermostat"
FAN_MODE_AUTO_LOW = "Auto Low"
FAN_MODE_CIRCULATE = "Circulate"
FAN_MODE_ON_LOW = "On Low"
HVAC_MODE_AUTO = "auto"
HVAC_MODE_COOL = "cool"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_OFF = "off"

CONF_ECO_HIGH_THRESHOLD = "eco_high_threshold"
CONF_ECO_LOW_THRESHOLD = "eco_low_threshold"
HANDLE_ECO_MODE = "eco_mode"

CONF_AQI_SENSOR = "aqi"
CONF_AQI_THRESHOLD = "aqi_threshold"

CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_INDOOR_TEMPERATURE_SENSOR = "indoor_temperature_sensor"

CONF_BRIGHTNESS_PERCENT_SENSOR = "sensor.outdoor_brightness_percent_sensor"
CONF_BRIGHTNESS_SENSOR = "sensor.outdoor_brightness_sensor"
CONF_OUTDOOR_BRIGHTNESS_PERCENT_SENSOR = "outdoor_brightness_percent_sensor"
CONF_OUTDOOR_BRIGHTNESS_SENSOR = "outdoor_brightness_sensor"

CONF_OUTDOOR_HIGH_THRESHOLD = "outdoor_high_threshold"
CONF_OUTDOOR_LOW_THRESHOLD = "outdoor_low_threshold"
CONF_OUTDOOR_TEMPERATURE_SENSOR = "outdoor_temperature_sensor"

EVENT_LIGHTNING_DETECTED = "LIGHTNING_DETECTED"
CONF_DISTANCE = "distance"
CONF_LIGHTNING_WINDOW = "notification_window_seconds"


class AdjustOnProximity(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to adjust climate based on proximity to home."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_arrive_home,
            EVENT_PRESENCE_CHANGE,
            new=self.presence_manager.HomeStates.just_arrived.value,
            first=True,
            constrain_enabled=True,
        )
        self.listen_event(
            self._on_proximity_change, EVENT_PROXIMITY_CHANGE, constrain_enabled=True
        )

    def _on_arrive_home(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Last ditch: turn the thermostat to home when someone arrives."""
        if self.climate_manager.away_mode:
            self.log('Last ditch: setting thermostat to "Home" (arrived)')
            self.climate_manager.set_home()

    def _on_proximity_change(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "PROXIMITY_CHANGE" events."""
        if self.climate_manager.outdoor_temperature_extreme:
            # Scenario 1: Anything -> Away (Extreme Temps)
            if (
                data["old"] != self.presence_manager.ProximityStates.away.value
                and data["new"] == self.presence_manager.ProximityStates.away.value
            ):
                self.climate_manager.set_away()

            # Scenario 2: Away -> Anything (Extreme Temps)
            elif (
                data["old"] == self.presence_manager.ProximityStates.away.value
                and data["new"] != self.presence_manager.ProximityStates.away.value
            ):
                self.climate_manager.set_home()
        else:
            # Scenario 3: Home -> Anything
            if (
                data["old"] == self.presence_manager.ProximityStates.home.value
                and data["new"] != self.presence_manager.ProximityStates.home.value
            ):
                self.climate_manager.set_away()

            # Scenario 4: Anything -> Nearby
            elif (
                data["old"] != self.presence_manager.ProximityStates.nearby.value
                and data["new"] == self.presence_manager.ProximityStates.nearby.value
            ):
                self.climate_manager.set_home()


class ClimateManager(Base):  # pylint: disable=too-many-public-methods
    """Define an app to represent climate control."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
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
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._away = False
        self._last_hvac_mode = None
        self._last_temperature = None

    @property
    def away_mode(self) -> bool:
        """Return the state of away mode."""
        return self._away

    @property
    def eco_high_temperature(self) -> int:
        """Return the upper limit of eco mode."""
        return self.get_state(self.entity_ids[CONF_ECO_HIGH_THRESHOLD])

    @property
    def eco_low_temperature(self) -> int:
        """Return the lower limit of eco mode."""
        return self.get_state(self.entity_ids[CONF_ECO_LOW_THRESHOLD])

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return self.get_state(self.entity_ids[CONF_THERMOSTAT], attribute="fan_mode")

    @property
    def indoor_humidity(self) -> float:
        """Return the average indoor humidity."""
        return float(self.get_state(self.entity_ids[CONF_HUMIDITY_SENSOR]))

    @property
    def indoor_temperature(self) -> float:
        """Return the average indoor temperature."""
        return float(self.get_state(self.entity_ids[CONF_INDOOR_TEMPERATURE_SENSOR]))

    @property
    def hvac_mode(self) -> str:
        """Return the current operating mode."""
        return self.get_state(self.entity_ids[CONF_THERMOSTAT])

    @property
    def outdoor_brightness(self) -> int:
        """Return the outdoor brightness in lux."""
        return int(self.get_state(self.entity_ids[CONF_BRIGHTNESS_SENSOR]))

    @property
    def outdoor_brightness_percentage(self) -> int:
        """Return the human-perception of brightness percentage."""
        return int(self.get_state(self.entity_ids[CONF_BRIGHTNESS_PERCENT_SENSOR]))

    @property
    def outdoor_high_temperature(self) -> float:
        """Return the upper limit of "extreme" outdoor temperatures."""
        return float(self.get_state(self.entity_ids[CONF_OUTDOOR_HIGH_THRESHOLD]))

    @property
    def outdoor_low_temperature(self) -> float:
        """Return the lower limit of "extreme" outdoor temperatures."""
        return float(self.get_state(self.entity_ids[CONF_OUTDOOR_LOW_THRESHOLD]))

    @property
    def outdoor_temperature(self) -> float:
        """Return the outdoor temperature."""
        return float(self.get_state(self.entity_ids[CONF_OUTDOOR_TEMPERATURE_SENSOR]))

    @property
    def outdoor_temperature_extreme(self) -> float:
        """Return whether the outside temperature is at extreme limits."""
        return (
            self.outdoor_temperature < self.outdoor_low_temperature
            or self.outdoor_temperature > self.outdoor_high_temperature
        )

    @property
    def target_temperature(self) -> int:
        """Return the temperature the thermostat is currently set to."""
        try:
            return int(
                self.get_state(
                    self.entity_ids[CONF_THERMOSTAT], attribute="temperature"
                )
            )
        except TypeError:
            return 0

    def _on_eco_temp_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """React when the temperature goes above or below its eco thresholds."""
        current_temperature = float(new)

        if (
            current_temperature > self.eco_high_temperature
            and self.hvac_mode != HVAC_MODE_COOL
        ):
            self.log(
                'Eco Mode: setting to "cool" ({0}°)'.format(self.eco_high_temperature)
            )
            self.set_mode_cool()
            self.set_temperature(self.eco_high_temperature)
        elif (
            current_temperature < self.eco_low_temperature
            and self.hvac_mode != HVAC_MODE_HEAT
        ):
            self.log(
                'Eco Mode: setting to "heat" ({0}°)'.format(self.eco_low_temperature)
            )
            self.set_mode_heat()
            self.set_temperature(self.eco_low_temperature)
        elif (
            self.eco_low_temperature <= current_temperature <= self.eco_high_temperature
            and self.hvac_mode != HVAC_MODE_OFF
        ):
            self.log('Within eco mode limits; turning thermostat to "off"')
            self.set_mode_off()

    def _set_fan_mode(self, fan_mode: str) -> None:
        """Set the themostat's fan mode."""
        if fan_mode == self.fan_mode:
            return

        self.log('Setting fan mode to "{0}"'.format(fan_mode.title()))
        self.call_service(
            "climate/set_fan_mode",
            entity_id=self.entity_ids[CONF_THERMOSTAT],
            fan_mode=fan_mode,
        )

    def _set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the themostat's operation mode."""
        if hvac_mode == self.hvac_mode:
            return

        self.log('Setting operation mode to "{0}"'.format(hvac_mode.title()))
        self.call_service(
            "climate/set_hvac_mode",
            entity_id=self.entity_ids[CONF_THERMOSTAT],
            hvac_mode=hvac_mode,
        )

    def bump_temperature(self, value: int) -> None:
        """Bump the current temperature."""
        if self.hvac_mode == HVAC_MODE_COOL:
            value *= -1
        self.set_temperature(self.target_temperature + value)

    def set_away(self) -> None:
        """Set the thermostat to away."""
        if self._away:
            return

        self.log('Setting thermostat to "Away" mode')

        self._away = True
        self._last_hvac_mode = self.hvac_mode
        self._last_temperature = self.target_temperature

        self.set_mode_off()

        self.handles[HANDLE_ECO_MODE] = self.listen_state(
            self._on_eco_temp_change, self.entity_ids[CONF_INDOOR_TEMPERATURE_SENSOR]
        )

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
        if not self._away:
            return

        self.log('Setting thermostat to "Home" mode')
        self._away = False

        handle = self.handles.pop(HANDLE_ECO_MODE)
        self.cancel_listen_state(handle)

        # If the thermostat isn't doing anything, set it to the previous settings
        # (before away mode); otherwise, let it keep doing its thing:
        if self.hvac_mode == HVAC_MODE_OFF:
            self._set_hvac_mode(self._last_hvac_mode)
            self.set_temperature(self._last_temperature)

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

    def set_temperature(self, temperature: int) -> None:
        """Set the thermostat temperature."""
        if temperature == self.target_temperature:
            return

        # If the thermostat is off and the temperature is adjusted,
        # make a guess as to which operation mode should be used:
        if self.hvac_mode == HVAC_MODE_OFF:
            if temperature > self.indoor_temperature:
                self.set_mode_heat()
            elif temperature < self.indoor_temperature:
                self.set_mode_cool()
            else:
                self.set_mode_auto()

        self.call_service(
            "climate/set_temperature",
            entity_id=self.entity_ids[CONF_THERMOSTAT],
            temperature=str(temperature),
        )


class LightningDetected(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify when lightning is detected."""

    def configure(self) -> None:
        """Configure."""
        self._active = False
        self._lock = Lock()

        self.listen_event(
            self._on_lightning_detected,
            EVENT_LIGHTNING_DETECTED,
            constrain_enabled=True,
        )

    def _on_lightning_detected(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "LIGHTNING_DETECTED" events."""
        with self._lock:
            if self._active:
                return

            send_notification(
                self,
                "presence:home",
                "Lightning detected {0} miles away.".format(data[CONF_DISTANCE]),
                title="Lightning Detected ⚡️",
            )

            self._active = True
            self.run_in(self._on_reset, self.properties[CONF_LIGHTNING_WINDOW])

    def _on_reset(self, kwargs: dict) -> None:
        """Reset the notification window."""
        self._active = False


class NotifyBadAqi(Base):
    """Define a feature to notify us of bad air quality."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_AQI_SENSOR): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_AQI_THRESHOLD): int}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._bad_notification_sent = False
        self._good_notification_sent = True
        self._send_notification_func = None  # type: Optional[Callable]

        self.listen_state(self._on_aqi_change, self.entity_ids[CONF_AQI_SENSOR])

    def _on_aqi_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send select notifications when cooling and poor AQI."""

        if self.climate_manager.hvac_mode != HVAC_MODE_COOL:
            return

        current_aqi = int(new)

        def _send_bad_notification():
            """Send a notification of bad AQI."""
            send_notification(
                self,
                "presence:home",
                "AQI is at {0}; consider closing the humidifier vent.".format(
                    current_aqi
                ),
                title="Poor AQI 😤",
            )

        def _send_good_notification():
            """Send a notification of good AQI."""
            send_notification(
                self,
                "presence:home",
                "AQI is at {0}; open the humidifer vent again.".format(current_aqi),
                title="Better AQI 😅",
            )

        if current_aqi > self.properties[CONF_AQI_THRESHOLD]:
            if self._bad_notification_sent:
                return

            self.log("Notifying anyone at home of bad AQI during cooling")
            self._bad_notification_sent = True
            self._good_notification_sent = False
            notification_func = _send_bad_notification
        else:
            if self._good_notification_sent:
                return

            self.log("Notifying anyone at home of AQI improvement during cooling")
            self._bad_notification_sent = False
            self._good_notification_sent = True
            notification_func = _send_good_notification

        # If the automation is enabled when a battery is low, send a notification;
        # if not, remember that we should send the notification when the automation
        # becomes enabled:
        if self.enabled:
            notification_func()
        else:
            self._send_notification_func = notification_func

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled (if appropriate)."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None
