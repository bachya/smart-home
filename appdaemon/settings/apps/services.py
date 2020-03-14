"""Define automations to call services in specific scenarios."""
# pylint: disable=too-few-public-methods
from random import choice
from typing import Union

import voluptuous as vol
from core import APP_SCHEMA, Base
from helpers import config_validation as cv

CONF_ABOVE = "above"
CONF_BELOW = "below"
CONF_DELAY = "delay"
CONF_EQUAL_TO = "equal_to"
CONF_NEW_TARGET_STATE = "new_target_state"
CONF_OLD_TARGET_STATE = "old_target_state"
CONF_RANDOM_TICK_LOWER_END = "lower_end"
CONF_RANDOM_TICK_UPPER_END = "upper_end"
CONF_RUN_ON_DAYS = "run_on_days"
CONF_SCHEDULE_TIME = "schedule_time"
CONF_SERVICE = "service"
CONF_SERVICES = "services"
CONF_SERVICE_DATA = "service_data"
CONF_SERVICE_DOWN = "service_down"
CONF_SERVICE_DOWN_DATA = "service_down_data"
CONF_SERVICE_ORDER = "service_order"
CONF_SERVICE_UP = "service_up"
CONF_SERVICE_UP_DATA = "service_up_data"
CONF_TARGET_ENTITY_ID = "target_entity_id"
CONF_TARGET_VALUE = "target_value"
CONF_ZWAVE_DEVICE = "zwave_device"

SERVICE_ORDER_RANDOM = "random"
SERVICE_ORDER_SEQUENTIAL = "sequential"
SERVICE_ORDER_OPTIONS = set([SERVICE_ORDER_RANDOM, SERVICE_ORDER_SEQUENTIAL])

DEFAULT_RANDOM_TICK_LOWER_END = 5 * 60
DEFAULT_RANDOM_TICK_UPPER_END = 60 * 60

HANDLE_TICK = "tick"

SERVICE_CALL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVICE): cv.string,
        vol.Optional(CONF_SERVICE_DATA, default={}): dict,
    }
)

SINGLE_SERVICE_SCHEMA = APP_SCHEMA.extend(
    {vol.Required(CONF_SERVICES): SERVICE_CALL_SCHEMA}
)

MULTI_SERVICE_SCHEMA = APP_SCHEMA.extend(
    {
        vol.Required(CONF_SERVICES): vol.All(cv.ensure_list, [SERVICE_CALL_SCHEMA]),
        vol.Optional(CONF_SERVICE_ORDER, default=SERVICE_ORDER_SEQUENTIAL): vol.In(
            SERVICE_ORDER_OPTIONS
        ),
    }
)


class MultiServiceBase(Base):
    """Define a base class for automations that handle multiple services."""

    def configure(self) -> None:
        """Configure."""
        self._count = 0

    def pick_and_call_service(self) -> None:
        """Run the correct service."""
        if self.args[CONF_SERVICE_ORDER] == SERVICE_ORDER_SEQUENTIAL:
            index = self._count % len(self.args[CONF_SERVICES])
            service_data = self.args[CONF_SERVICES][index]
        else:
            service_data = choice(self.args[CONF_SERVICES])  # nosec

        self.call_service(service_data[CONF_SERVICE], **service_data[CONF_SERVICE_DATA])

        self._count += 1


class ServiceOnRandomTick(MultiServiceBase):
    """Define an automation to call a service at random moments."""

    APP_SCHEMA = MULTI_SERVICE_SCHEMA.extend(
        {
            vol.Optional(
                CONF_RANDOM_TICK_LOWER_END, default=DEFAULT_RANDOM_TICK_LOWER_END
            ): cv.positive_int,
            vol.Optional(
                CONF_RANDOM_TICK_UPPER_END, default=DEFAULT_RANDOM_TICK_UPPER_END
            ): cv.positive_int,
        }
    )

    def configure(self) -> None:
        """Configure."""
        super().configure()
        self._start_ticking()

    def _start_ticking(self) -> None:
        """Start the "ticking" process."""
        self.data[HANDLE_TICK] = self.run_every(
            self._on_tick,
            self.datetime(),
            self.args[CONF_RANDOM_TICK_LOWER_END],
            random_end=self.args[CONF_RANDOM_TICK_UPPER_END],
        )

    def _on_tick(self, kwargs: dict) -> None:
        """Fire the event when the tick occurs."""
        self.pick_and_call_service()

    def on_disable(self) -> None:
        """Stop ticking when the automation is disabled."""
        if HANDLE_TICK in self.data:
            handle = self.data.pop(HANDLE_TICK)
            self.cancel_timer(handle)

    def on_enable(self) -> None:
        """Start ticking when the automation is enabled."""
        self._start_ticking()


class ServiceOnState(Base):
    """Define an automation to call a service upon seeing an entity in a state."""

    APP_SCHEMA = vol.All(
        SINGLE_SERVICE_SCHEMA.extend(
            {
                vol.Required(CONF_TARGET_ENTITY_ID): cv.entity_id,
                vol.Optional(CONF_NEW_TARGET_STATE): cv.string,
                vol.Optional(CONF_OLD_TARGET_STATE): cv.string,
                vol.Optional(CONF_DELAY): vol.All(
                    cv.time_period, lambda value: value.seconds
                ),
            },
            cv.has_at_least_one_key(CONF_NEW_TARGET_STATE, CONF_OLD_TARGET_STATE),
        )
    )

    def configure(self) -> None:
        """Configure."""
        kwargs = {}

        if CONF_NEW_TARGET_STATE in self.args:
            kwargs["new"] = self.args[CONF_NEW_TARGET_STATE]
        if CONF_OLD_TARGET_STATE in self.args:
            kwargs["old"] = self.args[CONF_OLD_TARGET_STATE]
        if CONF_DELAY in self.args:
            kwargs["duration"] = self.args[CONF_DELAY]

        self.listen_state(
            self._on_target_state_observed, self.args[CONF_TARGET_ENTITY_ID], **kwargs
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
        self.call_service(
            self.args[CONF_SERVICES][CONF_SERVICE],
            **self.args[CONF_SERVICES][CONF_SERVICE_DATA]
        )


class ServiceOnTime(Base):
    """Define an automation to call a service at a specific time."""

    APP_SCHEMA = SINGLE_SERVICE_SCHEMA.extend(
        {vol.Required(CONF_SCHEDULE_TIME): cv.time}
    )

    def configure(self) -> None:
        """Configure."""
        self.run_daily(self._on_time_reached, self.args[CONF_SCHEDULE_TIME])

    def _on_time_reached(self, kwargs: dict) -> None:
        """Call the service."""
        self.call_service(
            self.args[CONF_SERVICES][CONF_SERVICE],
            **self.args[CONF_SERVICES][CONF_SERVICE_DATA]
        )
