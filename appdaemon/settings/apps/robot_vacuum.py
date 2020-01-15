"""Define automations for robot vacuums."""
from datetime import timedelta
from enum import Enum
from typing import Callable, List, Optional, Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import CONF_ENTITY_IDS, CONF_NOTIFICATION_INTERVAL_SLIDER, CONF_PROPERTIES
from helpers import config_validation as cv
from notification import send_notification

CONF_BIN_STATE = "bin_state"
CONF_FULL_THRESHOLD_MINUTES = "full_threshold_minutes"
CONF_RUN_TIME = "run_time"
CONF_VACUUM = "vacuum"

CONF_CONSUMABLES = "consumables"
CONF_CONSUMABLE_THRESHOLD = "consumable_threshold"

CONF_CALENDAR = "calendar"
CONF_IOS_EMPTIED_KEY = "ios_emptied_key"

HANDLE_BIN_FULL = "bin_full"
HANDLE_NEXT_RUN_NOTIFICATION = "next_run_notification"
HANDLE_STUCK = "stuck"


class MonitorConsumables(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify when a consumable gets low."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_PROPERTIES): vol.Schema(
                {
                    vol.Required(CONF_CONSUMABLE_THRESHOLD): int,
                    vol.Required(CONF_CONSUMABLES): cv.ensure_list,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._consumables_met: List[str] = []
        self._send_notification_func: Optional[Callable] = None

        for consumable in self.properties[CONF_CONSUMABLES]:
            self.listen_state(
                self._on_consumable_change,
                self.app.entity_ids[CONF_VACUUM],
                attribute=consumable,
            )

    def _on_consumable_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Create a task when a consumable is getting low."""

        def _send_notification() -> None:
            """Send the notification."""
            send_notification(
                self, "slack:@aaron", f"Order a new Wolfie consumable: {attribute}"
            )

        if int(new) < self.properties[CONF_CONSUMABLE_THRESHOLD]:
            if attribute in self._consumables_met:
                return

            self._consumables_met.append(attribute)

            self.log("Consumable is low: %s", attribute)

            if self.enabled:
                _send_notification()
            else:
                self._send_notification_func = _send_notification
        else:
            if attribute not in self._consumables_met:
                return

            self._consumables_met.remove(attribute)

            self.log("Consumable is restored: %s", attribute)

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled (if appropriate)."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None


class NotifyBeforeRun(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify before Wolfie runs."""

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_next_run_datetime_change,
            self.app.entity_ids[CONF_CALENDAR],
            attribute="start_time",
        )

    def _on_next_run_datetime_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Schedule a notification for an hour before the next run."""
        if HANDLE_NEXT_RUN_NOTIFICATION in self.handles:
            handle = self.handles.pop(HANDLE_NEXT_RUN_NOTIFICATION)
            self.cancel_timer(handle)

        self.handles[HANDLE_NEXT_RUN_NOTIFICATION] = send_notification(
            self,
            "presence:home",
            "Make sure to pull the boundaries out!",
            title="Wolfie runs in 1 hour",
            when=self.parse_datetime(new) - timedelta(hours=1),
        )


class NotifyWhenRunComplete(Base):
    """Define a feature to notify when the vacuum cycle is complete."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_IDS): vol.Schema(
                {vol.Required(CONF_NOTIFICATION_INTERVAL_SLIDER): cv.entity_id},
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        if self.enabled and self.app.bin_state == self.app.BinStates.full:
            self._start_notification_cycle()

        self.listen_state(
            self._on_notification_interval_change,
            self.entity_ids[CONF_NOTIFICATION_INTERVAL_SLIDER],
        )
        self.listen_state(
            self._on_vacuum_bin_change, self.app.entity_ids[CONF_BIN_STATE]
        )

    def _cancel_notification_cycle(self) -> None:
        """Cancel any active notification."""
        if HANDLE_BIN_FULL in self.handles:
            cancel = self.handles.pop(HANDLE_BIN_FULL)
            cancel()

    def _on_notification_interval_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Reset the notification interval."""
        self._cancel_notification_cycle()
        if self.enabled and self.app.bin_state == self.app.BinStates.full:
            self._start_notification_cycle()

    def _on_vacuum_bin_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Deal with changes to the bin."""
        if self.enabled and new == self.app.BinStates.full.value:
            self._start_notification_cycle()
        elif old == self.app.BinStates.full.value:
            self._cancel_notification_cycle()

    def _start_notification_cycle(self) -> None:
        """Start a repeating notification sequence."""
        self._cancel_notification_cycle()

        self.handles[HANDLE_BIN_FULL] = send_notification(
            self,
            "presence:home",
            "Empty him now and you won't have to do it later!",
            title="Wolfie Full 🤖",
            when=self.datetime(),
            interval=int(
                float(
                    self.get_state(self.entity_ids[CONF_NOTIFICATION_INTERVAL_SLIDER])
                )
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
        if self.app.bin_state == self.app.BinStates.full:
            self._start_notification_cycle()


class NotifyWhenStuck(Base):
    """Define a feature to notify when the vacuum is stuck."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_IDS): vol.Schema(
                {vol.Required(CONF_NOTIFICATION_INTERVAL_SLIDER): cv.entity_id},
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        if self.enabled and self.app.state == self.app.States.error:
            self._start_notification_cycle()

        self.listen_state(self._on_error_change, self.app.entity_ids[CONF_VACUUM])
        self.listen_state(
            self._on_notification_interval_change,
            self.entity_ids[CONF_NOTIFICATION_INTERVAL_SLIDER],
        )

    def _cancel_notification_cycle(self) -> None:
        """Cancel any active notification."""
        if HANDLE_STUCK in self.handles:
            cancel = self.handles.pop(HANDLE_STUCK)
            cancel()

    def _on_error_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Notify when the vacuum is an error state."""
        if self.enabled and new == self.app.States.error.value:
            self._start_notification_cycle()
        elif old == self.app.States.error.value:
            self._cancel_notification_cycle()

    def _on_notification_interval_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Reset the notification interval."""
        self._cancel_notification_cycle()
        if self.enabled and self.app.state == self.app.States.error:
            self._start_notification_cycle()

    def _start_notification_cycle(self) -> None:
        """Start a repeating notification sequence."""
        self._cancel_notification_cycle()

        self.handles[HANDLE_STUCK] = send_notification(
            self,
            "presence:home",
            "Help him get back on track or home.",
            title="Wolfie Stuck 😢",
            when=self.datetime(),
            interval=int(
                float(
                    self.get_state(self.entity_ids[CONF_NOTIFICATION_INTERVAL_SLIDER])
                )
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
        if self.app.state == self.app.States.error:
            self._start_notification_cycle()


class Vacuum(Base):
    """Define an app to represent a vacuum-type appliance."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_IDS): vol.Schema(
                {
                    vol.Required(CONF_BIN_STATE): cv.entity_id,
                    vol.Required(CONF_VACUUM): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            )
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

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_cycle_done,
            self.entity_ids[CONF_VACUUM],
            old=self.States.returning.value,
            new=self.States.docked.value,
        )

        self.listen_state(
            self._on_schedule_start, self.entity_ids[CONF_CALENDAR], new="on"
        )

    @property
    def bin_state(self) -> "BinStates":
        """Define a property to get the bin state."""
        return self.BinStates(self.get_state(self.entity_ids[CONF_BIN_STATE]))

    @bin_state.setter
    def bin_state(self, value: "BinStates") -> None:
        """Set the bin state."""
        self.select_option(self.entity_ids[CONF_BIN_STATE], value.value)

    @property
    def run_time(self) -> int:
        """Return the most recent amount of running time."""
        return int(self.get_state(self.entity_ids[CONF_RUN_TIME]))

    @property
    def state(self) -> "States":
        """Define a property to get the state."""
        return self.States(self.get_state(self.entity_ids[CONF_VACUUM]))

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

        if self.run_time >= self.properties[CONF_FULL_THRESHOLD_MINUTES]:
            self.bin_state = self.BinStates.full

    def _on_schedule_start(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Start cleaning via the schedule."""
        self.start()

    def pause(self) -> None:
        """Pause the cleaning cycle."""
        self.call_service("vacuum/pause", entity_id=self.entity_ids[CONF_VACUUM])

    def start(self) -> None:
        """Start a cleaning cycle."""
        self.log("Starting vacuuming cycle")
        if self.security_manager.alarm_state == self.security_manager.AlarmStates.away:
            self.log('Changing alarm state to "Home"')
            self.security_manager.set_alarm(self.security_manager.AlarmStates.home)
        else:
            self.log("Activating vacuum")
            self.call_service("vacuum/start", entity_id=self.entity_ids[CONF_VACUUM])

    def stop(self) -> None:
        """Stop a vacuuming cycle."""
        self.log("Stopping vacuuming cycle")
        self.call_service(
            "vacuum/return_to_base", entity_id=self.entity_ids[CONF_VACUUM]
        )
