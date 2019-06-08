"""Define automations for climate control."""
from datetime import timedelta
from enum import Enum
from typing import Tuple

import voluptuous as vol

from const import CONF_ENTITY_IDS, EVENT_PRESENCE_CHANGE, EVENT_PROXIMITY_CHANGE
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.dt import ceil_dt

CONF_AVG_HUMIDITY_SENSOR = "average_humidity_sensor"
CONF_AVG_TEMP_SENSOR = "average_temperature_sensor"
CONF_OUTSIDE_TEMP = "outside_temp"
CONF_THERMOSTAT = "thermostat"

OUTSIDE_THRESHOLD_HIGH = 75
OUTSIDE_THRESHOLD_LOW = 35


class AdjustOnProximity(Base):
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

            self.climate_manager.set_away_mode(self.climate_manager.AwayModes.home)

    def _on_proximity_change(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "PROXIMITY_CHANGE" events."""
        if (
            self.climate_manager.outside_temp < OUTSIDE_THRESHOLD_LOW
            or self.climate_manager.outside_temp > OUTSIDE_THRESHOLD_HIGH
        ):

            # Scenario 1: Anything -> Away (Extreme Temps)
            if (
                data["old"] != self.presence_manager.ProximityStates.away.value
                and data["new"] == self.presence_manager.ProximityStates.away.value
            ):
                self.log('Setting thermostat to "Away" (extreme temp)')

                self.climate_manager.set_away_mode(self.climate_manager.AwayModes.away)

            # Scenario 2: Away -> Anything (Extreme Temps)
            elif (
                data["old"] == self.presence_manager.ProximityStates.away.value
                and data["new"] != self.presence_manager.ProximityStates.away.value
            ):
                self.log('Setting thermostat to "Home" (extreme temp)')

                self.climate_manager.set_away_mode(self.climate_manager.AwayModes.home)
        else:
            # Scenario 3: Home -> Anything
            if (
                data["old"] == self.presence_manager.ProximityStates.home.value
                and data["new"] != self.presence_manager.ProximityStates.home.value
            ):
                self.log('Setting thermostat to "Away"')

                self.climate_manager.set_away_mode(self.climate_manager.AwayModes.away)

            # Scenario 4: Anything -> Nearby
            elif (
                data["old"] != self.presence_manager.ProximityStates.nearby.value
                and data["new"] == self.presence_manager.ProximityStates.nearby.value
            ):
                self.log('Setting thermostat to "Home"')

                self.climate_manager.set_away_mode(self.climate_manager.AwayModes.home)


class ClimateManager(Base):
    """Define an app to represent climate control."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_AVG_HUMIDITY_SENSOR): cv.entity_id,
                    vol.Required(CONF_AVG_TEMP_SENSOR): cv.entity_id,
                    vol.Required(CONF_OUTSIDE_TEMP): cv.entity_id,
                    vol.Required(CONF_THERMOSTAT): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    class AwayModes(Enum):
        """Define an enum for thermostat away modes."""

        away = 1
        home = 2

    class FanModes(Enum):
        """Define an enum for thermostat fan modes."""

        auto = 1
        on = 2

    class Modes(Enum):
        """Define an enum for thermostat modes."""

        auto = 1
        cool = 2
        eco = 3
        heat = 4
        off = 5

    @property
    def average_indoor_humidity(self) -> float:
        """Return the average indoor humidity based on a list of sensors."""
        return float(self.get_state(self.entity_ids[CONF_AVG_HUMIDITY_SENSOR]))

    @property
    def average_indoor_temperature(self) -> float:
        """Return the average indoor temperature based on a list of sensors."""
        return float(self.get_state(self.entity_ids[CONF_AVG_TEMP_SENSOR]))

    @property
    def away_mode(self) -> bool:
        """Return the state of away mode."""
        return (
            self.get_state(self.entity_ids[CONF_THERMOSTAT], attribute="away_mode")
            == "on"
        )

    @property
    def indoor_temp(self) -> int:
        """Return the temperature the thermostat is currently set to."""
        try:
            return int(
                self.get_state(
                    self.entity_ids[CONF_THERMOSTAT], attribute="temperature"
                )
            )
        except TypeError:
            return 0

    @property
    def mode(self) -> "Modes":
        """Return the current operating mode."""
        return self.Modes[
            self.get_state(self.entity_ids[CONF_THERMOSTAT], attribute="operation_mode")
        ]

    @property
    def outside_temp(self) -> float:
        """Define a property to get the current outdoor temperature."""
        return float(self.get_state(self.entity_ids[CONF_OUTSIDE_TEMP]))

    def configure(self) -> None:
        """Configure."""
        self.register_endpoint(self._climate_bump_endpoint, "climate_bump")

    def _climate_bump_endpoint(self, data: dict) -> Tuple[dict, int]:
        """Define an endpoint to quickly bump the climate."""
        if not data.get("amount"):
            return ({"status": "error", "message": 'Missing "amount" parameter'}, 502)

        self.bump_indoor_temp(int(data["amount"]))

        return (
            {
                "status": "ok",
                "message": "Bumping temperature {0}°".format(data["amount"]),
            },
            200,
        )

    def bump_indoor_temp(self, value: int) -> None:
        """Bump the current temperature."""
        self.set_indoor_temp(self.indoor_temp + value)

    def set_away_mode(self, value: "AwayModes") -> None:
        """Set the state of away mode."""
        self.call_service("nest/set_away_mode", away_mode=value.name)

    def set_indoor_temp(self, value: int) -> None:
        """Set the thermostat temperature."""
        self.call_service(
            "climate/set_temperature",
            entity_id=self.entity_ids[CONF_THERMOSTAT],
            temperature=str(value),
        )

    def set_fan_mode(self, value: "FanModes") -> None:
        """Set the themostat's fan mode."""
        self.call_service(
            "climate/set_fan_mode",
            entity_id=self.entity_ids[CONF_THERMOSTAT],
            fan_mode=value.name,
        )

    def set_mode(self, value: "Modes") -> None:
        """Set the themostat's operating mode."""
        self.call_service(
            "climate/set_operation_mode",
            entity_id=self.entity_ids[CONF_THERMOSTAT],
            operation_mode=value.name,
        )


class CycleFan(Base):
    """Define a feature to cycle the whole-house fan."""

    CYCLE_MINUTES = 15

    def configure(self) -> None:
        """Configure."""
        self.register_constraint("constrain_extreme_temperature")

        cycle_on_dt = ceil_dt(self.datetime(), timedelta(minutes=self.CYCLE_MINUTES))
        cycle_off_dt = cycle_on_dt + timedelta(minutes=self.CYCLE_MINUTES)

        self.run_every(
            self.cycle_on, cycle_on_dt, 60 * 60, constrain_extreme_temperature=True
        )
        self.run_every(
            self.cycle_off, cycle_off_dt, 60 * 60, constrain_extreme_temperature=True
        )

    def constrain_extreme_temperature(self, value: bool) -> bool:
        """Constrain execution to whether the outside temp. is extreme."""
        return (
            self.climate_manager.outside_temp < OUTSIDE_THRESHOLD_LOW
            or self.climate_manager.outside_temp > OUTSIDE_THRESHOLD_HIGH
        )

    def cycle_off(self, kwargs: dict) -> None:
        """Turn off the whole-house fan."""
        self.climate_manager.set_fan_mode(self.climate_manager.FanModes.auto)

    def cycle_on(self, kwargs: dict) -> None:
        """Turn on the whole-house fan."""
        self.climate_manager.set_fan_mode(self.climate_manager.FanModes.on)
