"""Define automations to call services in specific scenarios."""
from random import randint
from typing import Union

import voluptuous as vol

from const import CONF_EVENT, CONF_EVENT_DATA, CONF_INTERVAL
from core import APP_SCHEMA, Base
from helpers import config_validation as cv

CONF_DELAY = "delay"
CONF_ENTITY_THRESHOLDS = "entity_thresholds"
CONF_NEW_TARGET_STATE = "new_target_state"
CONF_OLD_TARGET_STATE = "old_target_state"
CONF_RANDOM_TICK_LOWER_END = "lower_end"
CONF_RANDOM_TICK_UPPER_END = "upper_end"
CONF_RUN_ON_DAYS = "run_on_days"
CONF_SCHEDULE_TIME = "schedule_time"
CONF_SERVICE = "service"
CONF_SERVICE_ALTERNATE = "service_alternate"
CONF_SERVICE_DATA = "service_data"
CONF_SERVICE_DATA_ALTERNATE = "service_data_alternate"
CONF_SERVICE_DOWN = "service_down"
CONF_SERVICE_DOWN_DATA = "service_down_data"
CONF_SERVICE_UP = "service_up"
CONF_SERVICE_UP_DATA = "service_up_data"
CONF_TARGET_ENTITY_ID = "target_entity_id"
CONF_TARGET_VALUE = "target_value"
CONF_ZWAVE_DEVICE = "zwave_device"

DEFAULT_RANDOM_TICK_LOWER_END = 5 * 60
DEFAULT_RANDOM_TICK_UPPER_END = 60 * 60

HANDLE_TICK = "tick"

SERVICE_CALL_SCHEMA = APP_SCHEMA.extend(
    {vol.Required(CONF_SERVICE): str, vol.Optional(CONF_SERVICE_DATA, default={}): dict}
)


class ServiceOnEvent(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service upon seeing an specific event/payload."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {
            vol.Required(CONF_EVENT): cv.string,
            vol.Optional(CONF_EVENT_DATA, default={}): dict,
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_event_heard,
            self.properties[CONF_EVENT],
            **self.properties[CONF_EVENT_DATA],
        )

    def _on_event_heard(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Call the service."""
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceOnInterval(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service every X seconds."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {vol.Required(CONF_INTERVAL): cv.time_period}
    )

    def configure(self) -> None:
        """Configure."""
        self.run_every(
            self._on_interval_reached, self.datetime(), self.properties[CONF_INTERVAL]
        )

    def _on_interval_reached(self, kwargs: dict) -> None:
        """Call the service."""
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceOnRandomTick(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service at random moments."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {
            vol.Optional(CONF_SERVICE_ALTERNATE): cv.string,
            vol.Optional(CONF_SERVICE_DATA_ALTERNATE, default={}): dict,
            vol.Optional(
                CONF_RANDOM_TICK_LOWER_END, default=DEFAULT_RANDOM_TICK_LOWER_END,
            ): cv.positive_int,
            vol.Optional(
                CONF_RANDOM_TICK_UPPER_END, default=DEFAULT_RANDOM_TICK_UPPER_END,
            ): cv.positive_int,
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._count = 0
        self._start_ticking()

    def _start_ticking(self) -> None:
        """Start the "ticking" process."""
        self.handles[HANDLE_TICK] = self.run_every(
            self._on_tick,
            self.datetime(),
            randint(  # nosec
                self.properties[CONF_RANDOM_TICK_LOWER_END],
                self.properties[CONF_RANDOM_TICK_UPPER_END],
            ),
        )

    def _on_tick(self, kwargs: dict) -> None:
        """Fire the event when the tick occurs."""
        self._count += 1
        if CONF_SERVICE_ALTERNATE in self.args and self._count % 2 == 0:
            self.call_service(
                self.args[CONF_SERVICE_ALTERNATE],
                **self.args[CONF_SERVICE_DATA_ALTERNATE],
            )
        else:
            self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])

    def on_disable(self) -> None:
        """Stop ticking when the automation is disabled."""
        if HANDLE_TICK in self.handles:
            handle = self.handles.pop(HANDLE_TICK)
            self.cancel_timer(handle)

    def on_enable(self) -> None:
        """Start ticking when the automation is enabled."""
        self._start_ticking()


class ServiceOnState(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service upon seeing an entity in a state."""

    APP_SCHEMA = vol.All(
        SERVICE_CALL_SCHEMA.extend(
            {
                vol.Required(CONF_TARGET_ENTITY_ID): cv.entity_id,
                vol.Optional(CONF_NEW_TARGET_STATE): cv.string,
                vol.Optional(CONF_OLD_TARGET_STATE): cv.string,
                vol.Optional(CONF_DELAY): cv.time_period,
            },
            cv.has_at_least_one_key(CONF_NEW_TARGET_STATE, CONF_OLD_TARGET_STATE),
        ),
    )

    def configure(self) -> None:
        """Configure."""
        kwargs = {}

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
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceOnTime(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service at a specific time."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend({vol.Required(CONF_SCHEDULE_TIME): cv.time})

    def configure(self) -> None:
        """Configure."""
        self.run_daily(
            self._on_time_reached, self.parse_time(self.properties[CONF_SCHEDULE_TIME])
        )

    def _on_time_reached(self, kwargs: dict) -> None:
        """Call the service."""
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceOnZWaveSwitchDoubleTap(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service when a Z-Wave switch double-tap occurs."""

    APP_SCHEMA = vol.All(
        APP_SCHEMA.extend(
            {
                vol.Required(CONF_ZWAVE_DEVICE): cv.entity_id,
                vol.Inclusive(CONF_SERVICE_UP, "up"): cv.string,
                vol.Inclusive(CONF_SERVICE_UP_DATA, "up", default={}): dict,
                vol.Inclusive(CONF_SERVICE_DOWN, "down"): cv.string,
                vol.Inclusive(CONF_SERVICE_DOWN_DATA, "down", default={}): dict,
            }
        ),
        cv.has_at_least_one_key(CONF_SERVICE_UP, CONF_SERVICE_DOWN),
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_double_tap_up,
            "zwave.node_event",
            entity_id=self.entity_ids[CONF_ZWAVE_DEVICE],
            basic_level=255,
        )

        self.listen_event(
            self._on_double_tap_down,
            "zwave.node_event",
            entity_id=self.entity_ids[CONF_ZWAVE_DEVICE],
            basic_level=0,
        )

    def _on_double_tap_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Call the "down" service."""
        if CONF_SERVICE_DOWN not in self.args:
            self.log("No service defined for double-tap down")
            return

        self.call_service(
            self.args[CONF_SERVICE_DOWN], **self.args[CONF_SERVICE_DOWN_DATA]
        )

    def _on_double_tap_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Call the "up" service."""
        if CONF_SERVICE_UP not in self.args:
            self.log("No service defined for double-tap up")
            return

        self.call_service(self.args[CONF_SERVICE_UP], **self.args[CONF_SERVICE_UP_DATA])
