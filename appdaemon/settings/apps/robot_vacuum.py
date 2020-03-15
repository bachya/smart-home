"""Define automations for robot vacuums."""
from enum import Enum
from typing import Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.notification import send_notification

CONF_BIN_STATE = "bin_state"
CONF_CALENDAR = "calendar"
CONF_FULL_THRESHOLD_MINUTES = "full_threshold_minutes"
CONF_RUN_TIME = "run_time"
CONF_VACUUM = "vacuum"


class Vacuum(Base):
    """Define an app to represent a vacuum-type appliance."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_BIN_STATE): cv.entity_id,
            vol.Required(CONF_VACUUM): cv.entity_id,
        }
    )

    class BinStates(Enum):
        """Define an enum for vacuum bin states."""

        empty = "Empty"
        full = "Full"

    class States(Enum):
        """Define an enum for vacuum states."""

        cleaning = "cleaning"
        docked = "docked"
        error = "error"
        idle = "idle"
        paused = "paused"
        returning = "returning"
        unavailable = "unavailable"

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_cycle_done,
            self.args[CONF_VACUUM],
            old=self.States.returning.value,
            new=self.States.docked.value,
        )

        self.listen_state(self._on_schedule_start, self.args[CONF_CALENDAR], new="on")

    @property
    def bin_state(self) -> "BinStates":
        """Define a property to get the bin state."""
        return self.BinStates(self.get_state(self.args[CONF_BIN_STATE]))

    @bin_state.setter
    def bin_state(self, value: "BinStates") -> None:
        """Set the bin state."""
        self.select_option(self.args[CONF_BIN_STATE], value.value)

    @property
    def run_time(self) -> int:
        """Return the most recent amount of running time."""
        return int(self.get_state(self.args[CONF_RUN_TIME]))

    @property
    def state(self) -> "States":
        """Define a property to get the state."""
        return self.States(self.get_state(self.args[CONF_VACUUM]))

    def _on_cycle_done(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Re-arm security (if needed) when done."""
        self.log("Vacuuming cycle all done")
        if self.presence_manager.noone(
            self.presence_manager.HomeStates.just_arrived,
            self.presence_manager.HomeStates.home,
        ):
            self.log('Changing alarm state to "away"')
            self.security_manager.set_alarm(self.security_manager.AlarmStates.away)

        if self.run_time >= self.args[CONF_FULL_THRESHOLD_MINUTES]:
            self.bin_state = self.BinStates.full

    def _on_schedule_start(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Start cleaning via the schedule."""
        # self.start()
        send_notification(
            self,
            "mobile_app_brittany_bachs_iphone",
            "🤖 Wolfie is scheduled to run.",
            "Time to run Wolfie",
        )

    def pause(self) -> None:
        """Pause the cleaning cycle."""
        self.call_service("vacuum/pause", entity_id=self.args[CONF_VACUUM])

    def start(self) -> None:
        """Start a cleaning cycle."""
        self.log("Starting vacuuming cycle")
        if self.security_manager.alarm_state == self.security_manager.AlarmStates.away:
            self.log('Changing alarm state to "Home"')
            self.security_manager.set_alarm(self.security_manager.AlarmStates.home)
        else:
            self.log("Activating vacuum")
            self.call_service("vacuum/start", entity_id=self.args[CONF_VACUUM])

    def stop(self) -> None:
        """Stop a vacuuming cycle."""
        self.log("Stopping vacuuming cycle")
        self.call_service("vacuum/return_to_base", entity_id=self.args[CONF_VACUUM])
