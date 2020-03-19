"""Define automations for washer/dryer appliances."""
from datetime import timedelta
from enum import Enum
from typing import Union

import voluptuous as vol

from const import CONF_NOTIFICATION_INTERVAL_SLIDER
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.notification import send_notification

CONF_POWER = "power"
CONF_STATUS = "status"
CONF_CLEAN_THRESHOLD = "clean_threshold"
CONF_DRYING_THRESHOLD = "drying_threshold"
CONF_IOS_EMPTIED_KEY = "ios_emptied_key"
CONF_RUNNING_THRESHOLD = "running_threshold"

HANDLE_CLEAN = "clean"


class NotifyDone(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify a target when the appliancer is done."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_NOTIFICATION_INTERVAL_SLIDER): cv.entity_id,
            vol.Required(CONF_CLEAN_THRESHOLD): vol.Coerce(float),
            vol.Required(CONF_DRYING_THRESHOLD): vol.Coerce(float),
            vol.Required(CONF_IOS_EMPTIED_KEY): cv.string,
            vol.Required(CONF_RUNNING_THRESHOLD): vol.Coerce(float),
        }
    )

    def configure(self) -> None:
        """Configure."""
        if self.enabled and self.app.state == self.app.States.clean:
            self._start_notification_cycle()

        self.listen_state(
            self._on_notification_interval_change,
            self.args[CONF_NOTIFICATION_INTERVAL_SLIDER],
        )
        self.listen_state(self._on_power_change, self.app.args[CONF_POWER])
        self.listen_state(self._on_status_change, self.app.args[CONF_STATUS])

    def _cancel_notification_cycle(self) -> None:
        """Cancel any active notification."""
        if HANDLE_CLEAN in self.data:
            cancel = self.data.pop(HANDLE_CLEAN)
            cancel()

    def _on_notification_interval_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Reset the notification interval."""
        self._cancel_notification_cycle()
        if self.enabled and self.app.state == self.app.States.clean:
            self._start_notification_cycle()

    def _on_power_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Deal with changes to the power draw."""
        power = float(new)
        if (
            self.app.state != self.app.States.running
            and power >= self.args[CONF_RUNNING_THRESHOLD]
        ):
            self.log('Setting dishwasher to "Running"')
            self.app.state = self.app.States.running
        elif (
            self.app.state == self.app.States.running
            and power <= self.args[CONF_DRYING_THRESHOLD]
        ):
            self.log('Setting dishwasher to "Drying"')
            self.app.state = self.app.States.drying
        elif (
            self.app.state == self.app.States.drying
            and power == self.args[CONF_CLEAN_THRESHOLD]
        ):
            self.log('Setting dishwasher to "Clean"')
            self.app.state = self.app.States.clean

    def _on_status_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Deal with changes to the status."""
        if self.enabled and new == self.app.States.clean.value:
            self._start_notification_cycle()
        elif old == self.app.States.clean.value:
            self._cancel_notification_cycle()

    def _start_notification_cycle(self) -> None:
        """Start the repeating notification sequence."""
        self._cancel_notification_cycle()

        self.data[HANDLE_CLEAN] = send_notification(
            self,
            "presence:home",
            "Empty it now and you won't have to do it later!",
            title="🍽 Dishwasher Clean",
            when=self.datetime() + timedelta(minutes=15),
            interval=int(
                float(self.get_state(self.args[CONF_NOTIFICATION_INTERVAL_SLIDER]))
            )
            * 60
            * 60,
            data={"push": {"category": "dishwasher"}},
        )

    def on_disable(self) -> None:
        """Stop notifying when the automation is disabled."""
        self._cancel_notification_cycle()

    def on_enable(self) -> None:
        """Start notifying when the automation is enabled (if appropriate)."""
        if self.app.state == self.app.States.clean:
            self._start_notification_cycle()


class WasherDryer(Base):  # pylint: disable=too-few-public-methods
    """Define an app to represent a washer/dryer-type appliance."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_POWER): cv.entity_id,
            vol.Required(CONF_STATUS): cv.entity_id,
        }
    )

    class States(Enum):
        """Define an enum for states."""

        clean = "Clean"
        dirty = "Dirty"
        drying = "Drying"
        running = "Running"

    @property
    def state(self) -> "States":
        """Get the state."""
        return self.States(self.get_state(self.args[CONF_STATUS]))

    @state.setter
    def state(self, value: "States") -> None:
        """Set the state."""
        self.select_option(self.args[CONF_STATUS], value.value)
