"""Define automations to call services in specific scenarios."""
from typing import Union

import voluptuous as vol

from const import (
    CONF_ENTITY_IDS,
    CONF_EVENT,
    CONF_EVENT_DATA,
    CONF_PROPERTIES,
)
from core import APP_SCHEMA, Base
from helpers import config_validation as cv

CONF_TARGET_ENTITY_ID = "target_entity_id"

CONF_RUN_ON_DAYS = "run_on_days"
CONF_SCHEDULE_TIME = "schedule_time"

CONF_SERVICE = "service"
CONF_SERVICE_DATA = "service_data"

CONF_ENTITY_THRESHOLDS = "entity_thresholds"
CONF_TARGET_VALUE = "target_value"

CONF_DELAY = "delay"
CONF_NEW_TARGET_STATE = "new_target_state"
CONF_OLD_TARGET_STATE = "old_target_state"

CONF_SERVICE_DOWN = "service_down"
CONF_SERVICE_DOWN_DATA = "service_down_data"
CONF_SERVICE_UP = "service_up"
CONF_SERVICE_UP_DATA = "service_up_data"
CONF_ZWAVE_DEVICE = "zwave_device"

SERVICE_CALL_SCHEMA = APP_SCHEMA.extend(
    {vol.Required(CONF_SERVICE): str, vol.Required(CONF_SERVICE_DATA): dict}
)


class ServiceOnEvent(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service upon seeing an specific event/payload."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_EVENT): str, vol.Optional(CONF_EVENT_DATA): dict},
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_event_heard,
            self.properties[CONF_EVENT],
            **self.properties.get(CONF_EVENT_DATA, {}),
            constrain_enabled=True,
        )

    def _on_event_heard(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Call the service."""
        self.log(
            "Calling service (%s, %s) from event (%s, %s)",
            self.args[CONF_SERVICE],
            self.args[CONF_SERVICE_DATA],
            self.properties[CONF_EVENT],
            self.properties.get(CONF_EVENT_DATA, {}),
        )
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceOnState(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service upon seeing an entity in a state."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_TARGET_ENTITY_ID): cv.entity_id},
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.All(
                vol.Schema(
                    {
                        vol.Optional(CONF_NEW_TARGET_STATE): str,
                        vol.Optional(CONF_OLD_TARGET_STATE): str,
                        vol.Optional(CONF_DELAY): int,
                    },
                    extra=vol.ALLOW_EXTRA,
                ),
                cv.has_at_least_one_key(CONF_NEW_TARGET_STATE, CONF_OLD_TARGET_STATE),
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        kwargs = {"constrain_enabled": True, "auto_constraints": True}

        if CONF_NEW_TARGET_STATE in self.properties:
            kwargs["new"] = self.properties[CONF_NEW_TARGET_STATE]
        if CONF_OLD_TARGET_STATE in self.properties:
            kwargs["old"] = self.properties[CONF_OLD_TARGET_STATE]
        if CONF_DELAY in self.properties:
            kwargs["duration"] = self.properties[CONF_DELAY]

        self.listen_state(
            self._on_target_state_observed,
            self.entity_ids[CONF_TARGET_ENTITY_ID],
            **kwargs,
        )

    def _on_target_state_observed(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Call the service."""
        # In some cases – like the sun.sun entity – state change updates are published
        # even if the state value itself does not change; these events can cause this to
        # trigger unnecessarily. So, return if the old and new state values equal one
        # another:
        if new == old:
            return

        self.log(
            "Calling service (%s, %s) from state (%s, %s -> %s)",
            self.args[CONF_SERVICE],
            self.args[CONF_SERVICE_DATA],
            entity,
            old,
            new,
        )
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceOnTime(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service at a specific time."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_SCHEDULE_TIME): str}, extra=vol.ALLOW_EXTRA
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.run_daily(
            self._on_time_reached,
            self.parse_time(self.properties[CONF_SCHEDULE_TIME]),
            constrain_enabled=True,
            auto_constraints=True,
        )

    def _on_time_reached(self, kwargs: dict) -> None:
        """Call the service."""
        self.log(
            "Calling service (%s, %s) at time (%s)",
            self.args[CONF_SERVICE],
            self.args[CONF_SERVICE_DATA],
            self.properties[CONF_SCHEDULE_TIME],
        )
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceOnZWaveSwitchDoubleTap(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service when a Z-Wave switch double-tap occurs."""

    APP_SCHEMA = vol.All(
        APP_SCHEMA.extend(
            {
                CONF_ENTITY_IDS: vol.Schema(
                    {vol.Required(CONF_ZWAVE_DEVICE): cv.entity_id},
                    extra=vol.ALLOW_EXTRA,
                ),
                vol.Inclusive(CONF_SERVICE_UP, "up"): str,
                vol.Inclusive(CONF_SERVICE_UP_DATA, "up"): dict,
                vol.Inclusive(CONF_SERVICE_DOWN, "down"): str,
                vol.Inclusive(CONF_SERVICE_DOWN_DATA, "down"): dict,
            }
        ),
        cv.has_at_least_one_key(CONF_SERVICE_UP, CONF_SERVICE_DOWN),
        extra=vol.ALLOW_EXTRA,
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_double_tap_up,
            "zwave.node_event",
            entity_id=self.entity_ids[CONF_ZWAVE_DEVICE],
            basic_level=255,
            constrain_enabled=True,
        )

        self.listen_event(
            self._on_double_tap_down,
            "zwave.node_event",
            entity_id=self.entity_ids[CONF_ZWAVE_DEVICE],
            basic_level=0,
            constrain_enabled=True,
        )

    def _on_double_tap_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Call the "down" service."""
        self.log(
            "Calling service (%s, %s) from double tab down (%s)",
            self.args[CONF_SERVICE],
            self.args[CONF_SERVICE_DATA],
            self.entity_ids[CONF_ZWAVE_DEVICE],
        )
        self.call_service(
            self.args[CONF_SERVICE_DOWN], **self.args[CONF_SERVICE_DOWN_DATA]
        )

    def _on_double_tap_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Call the "up" service."""
        self.log(
            "Calling service (%s, %s) from double tab up (%s)",
            self.args[CONF_SERVICE],
            self.args[CONF_SERVICE_DATA],
            self.entity_ids[CONF_ZWAVE_DEVICE],
        )
        self.call_service(self.args[CONF_SERVICE_UP], **self.args[CONF_SERVICE_UP_DATA])
