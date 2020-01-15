"""Define PINs (locks, security system, etc.) and a PIN manager AppDaemon app."""
import random
from datetime import datetime, time
from enum import Enum
from threading import Lock
from typing import Generator, Optional, Tuple, Union

import voluptuous as vol
from const import CONF_PROPERTIES
from core import APP_SCHEMA, Base  # pylint: disable=no-name-in-module
from util.string import slugify

CONF_CODE_SLOT = "code_slot"
CONF_ENABLED_ENTITY_ID_STUB = "entity_id_stub"
CONF_ENTITY_ID = "entity_id"
CONF_NODE_ID = "node_id"
CONF_SYSTEM_ID = "system_id"

HANDLE_ONE_TIME_STUB = "one_time_{0}"
HANDLE_SCHEDULED_END = "scheduled_end"
HANDLE_SCHEDULED_START = "scheduled_start"

SIMPLISAFE_ENTITY_ID = "alarm_control_panel.8673_e_55th_avenue"

DOOR_FRONT_DOOR = "Front Door"
DOOR_GARAGE_FIRE_DOOR = "Garage Fire Door"
ZWAVE_LOCKS = {
    DOOR_FRONT_DOOR: {
        CONF_ENABLED_ENTITY_ID_STUB: "input_boolean.{0}_front_door",
        CONF_ENTITY_ID: "lock.front_door",
        CONF_NODE_ID: 16,
    },
    DOOR_GARAGE_FIRE_DOOR: {
        CONF_ENABLED_ENTITY_ID_STUB: "input_boolean.{0}_garage_fire_door",
        CONF_ENTITY_ID: "lock.garage_fire_door",
        CONF_NODE_ID: 8,
    },
}
ZWAVE_CHANGED_MESSAGE_STUB = "Unlocked with Keypad by user {0}"


class PinScheduleType(Enum):
    """Define PIN types (related to how long they are active)."""

    always = "Always"
    one_time = "One-Time"
    scheduled = "Scheduled"


class PIN(Base):  # pylint: disable=too-many-instance-attributes
    """Define a generic PIN manager."""

    def configure(self) -> None:
        """Configure."""
        self._reset_lock = Lock()

        self._end_entity_id = f"input_datetime.{self.name}_end"
        self._name_entity_id = f"input_text.{self.name}_name"
        self._schedule_type_entity_id = f"input_select.{self.name}_type"
        self._start_entity_id = f"input_datetime.{self.name}_start"
        self._value_entity_id = f"input_text.{self.name}_code"

        self.listen_event(self._on_execute_clicked, "PIN_EXECUTE", id=self.name)
        self.listen_event(self._on_reset_clicked, "PIN_RESET", id=self.name)

        if self.schedule_type == PinScheduleType.one_time:
            self.log("Re-establishing one-time PIN")
            self._listen_for_otp_use()
        elif self.schedule_type == PinScheduleType.scheduled:
            self.log("Re-establishing scheduled PIN")
            self._add_pin_during_schedule()

    @property
    def active(self) -> bool:
        """Return whether this PIN is in use."""
        return self.label != "" and self.value != ""

    @property
    def label(self) -> str:
        """Return the label of the PIN in the UI."""
        return self.get_state(self._name_entity_id)

    @label.setter
    def label(self, value: str) -> None:
        """Set the label of the PIN in the UI."""
        self.set_textvalue(self._name_entity_id, value)

    @property
    def schedule_end(self) -> datetime:
        """Return the schedule end date/time of the PIN in the UI."""
        return datetime.strptime(
            self.get_state(self._end_entity_id), "%Y-%m-%d %H:%M:%S"
        )

    @schedule_end.setter
    def schedule_end(self, value: datetime) -> None:
        """Set the schedule end date/time of the PIN in the UI."""
        self.call_service(
            "input_datetime/set_datetime",
            entity_id=self._end_entity_id,
            datetime=value.isoformat(),
        )

    @property
    def schedule_start(self) -> datetime:
        """Return the schedule start date/time of the PIN in the UI."""
        return datetime.strptime(
            self.get_state(self._start_entity_id), "%Y-%m-%d %H:%M:%S"
        )

    @schedule_start.setter
    def schedule_start(self, value: datetime) -> None:
        """Set the schedule start date/time of the PIN in the UI."""
        self.call_service(
            "input_datetime/set_datetime",
            entity_id=self._start_entity_id,
            datetime=value.isoformat(),
        )

    @property
    def schedule_type(self) -> Optional[PinScheduleType]:
        """Return the schedule type of the PIN in the UI."""
        raw_state = self.get_state(self._schedule_type_entity_id)

        try:
            return PinScheduleType(raw_state)
        except KeyError:
            self.error("Unknown PIN schedule type: %s", raw_state)
            return None

    @schedule_type.setter
    def schedule_type(self, value: PinScheduleType) -> None:
        """Set the schedule type of the PIN in the UI."""
        self.select_option(self._schedule_type_entity_id, value.value)

    @property
    def value(self) -> str:
        """Return the value of the PIN in the UI."""
        return self.get_state(self._value_entity_id)

    @value.setter
    def value(self, value: str) -> None:
        """Set the value of the PIN in the UI."""
        self.set_textvalue(self._value_entity_id, value)

    def _add_pin_during_schedule(self) -> None:
        """Schedule a scheduled PIN."""
        now = datetime.now()

        if now > self.schedule_start:
            self.log("Starting date/time for scheduled PIN can't be in the past")
            self.schedule_start = now
        else:
            self.handles[HANDLE_SCHEDULED_START] = self.run_at(
                self._set_scheduled_pin_cb, self.schedule_start
            )

        if now > self.schedule_end:
            self.log("Ending date/time for scheduled PIN can't be in the past")
            return

        self.handles[HANDLE_SCHEDULED_END] = self.run_at(
            self._remove_scheduled_pin_cb, self.schedule_end
        )

    def _listen_for_otp_use(self) -> None:
        """Listen for the use of a one-time PIN."""
        raise NotImplementedError()

    def _on_execute_clicked(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond when the execute button is clicked."""
        if not self.label or not self.value:
            self.log("Refusing to add an empty PIN")
            return

        if self.schedule_type == PinScheduleType.one_time:
            # The PIN is set until it gets used (after which it is automatically
            # removed):
            self.log("Adding one-time PIN")
            self.set_pin()
            self._listen_for_otp_use()
        elif self.schedule_type == PinScheduleType.scheduled:
            # The PIN is set at the start date/time and is automatically removed at the
            # end date/time:
            self.log(
                f"Adding scheduled PIN ({self.schedule_start} -> {self.schedule_end})"
            )
            self._add_pin_during_schedule()
        else:
            # The PIN is set forever (until manually removed):
            self.log("Adding permanent PIN")
            self.set_pin()

    def _on_reset_clicked(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond when the reset button is clicked."""
        self.log("Resetting PIN")
        self.reset()

    def _on_otp_used(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Respond when a one-time PIN is used."""
        if not self._pin_is_otp(new):
            return

        self.log("Removing one-time PIN")
        self.reset()

    def _pin_is_otp(self, pin: str) -> bool:
        """Return whether a detected PIN is a valid one-time PIN."""
        raise NotImplementedError()

    def _remove_scheduled_pin_cb(self, kwargs: dict) -> None:
        """Define a scheduler callback for removing a pin."""
        self.log("PIN schedule ended")
        self.reset()

    def _set_scheduled_pin_cb(self, kwargs: dict) -> None:
        """Define a scheduler callback for setting a pin."""
        self.log("PIN schedule starting")
        self.set_pin()

    def clear_handles(self) -> None:
        """Clear any Scheduled or One-Time handles."""
        if HANDLE_SCHEDULED_START in self.handles:
            for handle in (HANDLE_SCHEDULED_START, HANDLE_SCHEDULED_END):
                timer = self.handles.pop(handle)
                self.cancel_timer(timer)

        for handle in [handle for handle in self.handles if "one_time" in handle]:
            timer = self.handles.pop(handle)
            self.cancel_listen_state(timer)

    def remove_pin(self) -> None:
        """Remove the PIN."""
        raise NotImplementedError()

    def reset(self):
        """Reset the PIN."""
        with self._reset_lock:
            self.remove_pin()
            self.clear_handles()
            self.reset_ui()

    def reset_ui(self) -> None:
        """Reset the UI."""
        self.label = ""
        self.schedule_type = PinScheduleType.always
        self.schedule_end = datetime.now()
        self.schedule_start = datetime.now()
        self.value = ""

    def set_pin(self) -> None:
        """Set the PIN."""
        raise NotImplementedError()


class SimpliSafePIN(PIN):
    """Define a PIN manager for a SimpliSafe security system."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_PROPERTIES): vol.Schema(
                {vol.Required(CONF_SYSTEM_ID): int}, extra=vol.ALLOW_EXTRA
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        super().configure()

        self._system_id = self.properties[CONF_SYSTEM_ID]

    def _listen_for_otp_use(self) -> None:
        """Listen for the use of a one-time PIN."""
        self.handles[HANDLE_ONE_TIME_STUB.format(self.name)] = self.listen_state(
            self._on_otp_used, SIMPLISAFE_ENTITY_ID, attribute="changed_by"
        )

    def _pin_is_otp(self, pin: str) -> bool:
        """Return whether a detected PIN is a valid one-time PIN."""
        return pin == self.label

    def remove_pin(self) -> None:
        """Remove the PIN from SimpliSafe."""
        self.call_service(
            "simplisafe/remove_pin", system_id=self._system_id, label_or_pin=self.label
        )

    def set_pin(self) -> None:
        """Add the pin to SimpliSafe."""
        self.call_service(
            "simplisafe/set_pin",
            system_id=self._system_id,
            label=self.label,
            pin=self.value,
        )


class ZWaveLockPIN(PIN):
    """Define a PIN manager for Z-Wave locks."""

    def configure(self) -> None:
        """Configure."""
        super().configure()

        self._code_slot = self.properties[CONF_CODE_SLOT]

        self.run_daily(self._on_midnight_reached, time(0, 0, 0))

    def _get_locks(self, *, active_only: bool = True) -> Generator[Tuple, None, None]:
        """Return a generator of all locks (entity ID, enabled, name, and attrs)."""
        for lock_name, attrs in ZWAVE_LOCKS.items():
            enabled_entity_id = attrs[  # type: ignore
                CONF_ENABLED_ENTITY_ID_STUB
            ].format(self.name)
            enabled = self.get_state(enabled_entity_id) == "on"
            if active_only and not enabled:
                continue
            yield enabled_entity_id, lock_name, attrs

    def _listen_for_otp_use(self) -> None:
        """Listen for the use of a one-time PIN."""
        for _, name, attrs in self._get_locks():
            self.handles[
                HANDLE_ONE_TIME_STUB.format(slugify(name))
            ] = self.listen_state(
                self._on_otp_used, attrs[CONF_ENTITY_ID], attribute="lock_status"
            )

    def _on_midnight_reached(self, kwargs: dict) -> None:
        """Cycle new codes into empty slots (for extra security on open-zwave bug)."""
        if self.active:
            return

        self.log("Recycling code")
        self.remove_pin()

    def _pin_is_otp(self, pin: str) -> bool:
        """Return whether a detected PIN is a valid one-time PIN."""
        return pin == ZWAVE_CHANGED_MESSAGE_STUB.format(self._code_slot)

    def remove_pin(self) -> None:
        """
        "Remove" the PIN from any active locks.

        Because of a bug in Home Assistant's fork of open-zwave, we can't clear
        user codes from Z-Wave locks... As a compromise, we set the code to a random
        value.

        Note that this occurs to all locks, regardless of whether they're "active" or
        not.
        """
        for _, _, attrs in self._get_locks(active_only=False):
            self.call_service(
                "lock/set_usercode",
                node_id=attrs[CONF_NODE_ID],
                code_slot=self._code_slot,
                usercode=str(random.randint(0, 99999)).zfill(5),  # nosec
            )

    def reset_ui(self) -> None:
        """Reset the UI."""
        super().reset_ui()

        for _, _, attrs in self._get_locks():
            self.turn_off(attrs[CONF_ENABLED_ENTITY_ID_STUB].format(self.name))

    def set_pin(self) -> None:
        """Add the pin to any active locks."""
        for _, _, attrs in self._get_locks():
            self.call_service(
                "lock/set_usercode",
                node_id=attrs[CONF_NODE_ID],
                code_slot=self._code_slot,
                usercode=self.value,
            )
