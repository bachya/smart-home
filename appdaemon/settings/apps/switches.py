"""Define automations for switches."""
# pylint: disable=attribute-defined-outside-init,unused-argument
from datetime import timedelta
from random import randint
from typing import Callable, Union

from automation import Automation  # type: ignore
from const import (  # type: ignore
    BLACKOUT_END, BLACKOUT_START, THRESHOLD_CLOUDY)
from util.scheduler import run_on_days  # type: ignore

HANDLE_TIMER = 'timer'
HANDLE_TOGGLE_IN_WINDOW = 'in_window'
HANDLE_TOGGLE_OUT_WINDOW = 'out_window'
HANDLE_TOGGLE_STATE = 'toggle_state'
HANDLE_VACATION_MODE = 'vacation_mode'


class BaseSwitch(Automation):
    """Define a base feature for all switches."""

    @property
    def state(self) -> bool:
        """Return the current state of the switch."""
        return self.get_state(self.entity_ids['switch'])

    def attach_constraints(self, func: Callable) -> None:
        """Attach values from possible_constraints to a function."""
        if self.properties.get('possible_constraints'):
            for name, value in self.properties['possible_constraints'].items():
                func({name: value})
        else:
            func()

    def toggle(self, *, state: str = None, opposite_of: str = None) -> None:
        """Toggle the switch state."""
        if not state and not opposite_of:
            self._log.error('No state value provided')
            return

        if state:
            _state = state
        elif opposite_of == 'off':
            _state = 'on'
        else:
            _state = 'off'

        if self.state == 'off' and _state == 'on':
            self._log.info('Turning on: %s', self.entity_ids['switch'])

            self.turn_on(self.entity_ids['switch'])
        elif self.state == 'on' and _state == 'off':
            self._log.info('Turning off: %s', (self.entity_ids['switch']))

            self.turn_off(self.entity_ids['switch'])

    def toggle_on_schedule(self, kwargs: dict) -> None:
        """Turn off the switch at a certain time."""
        if kwargs.get('opposite'):
            self.toggle(opposite_of=kwargs['state'])
        else:
            self.toggle(state=kwargs['state'])


class BaseZwaveSwitch(BaseSwitch):
    """Define a Zwave switch."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_event(
            self.double_up,
            'zwave.node_event',
            entity_id=self.entity_ids['zwave_device'],
            basic_level=255,
            constrain_input_boolean=self.enabled_entity_id)

        self.listen_event(
            self.double_down,
            'zwave.node_event',
            entity_id=self.entity_ids['zwave_device'],
            basic_level=0,
            constrain_input_boolean=self.enabled_entity_id)

    def double_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Stub out method signature."""
        pass

    def double_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Stub out method signature."""
        pass


class DoubleTapTimerSwitch(BaseZwaveSwitch):
    """Define a feature to double tap a switch on for a time."""

    def double_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on the target timer slider with a double up tap."""
        self.set_value(
            self.entity_ids['timer_slider'],
            round(self.properties['duration'] / 60))


class DoubleTapToggleSwitch(BaseZwaveSwitch):
    """Define a feature to toggle a switch with a double tab of this switch."""

    def double_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn off the target switch with a double down tap."""
        self.turn_off(self.entity_ids['target'])

    def double_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on the target switch with a double up tap."""
        self.turn_on(self.entity_ids['target'])


class PresenceFailsafe(BaseSwitch):
    """Define a feature to restrict activation when we're not home."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.switch_activated,
            self.entity_ids['switch'],
            new='on',
            constrain_noone='just_arrived,home',
            constrain_input_boolean=self.enabled_entity_id)

    def switch_activated(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Turn the switch off if no one is home."""
        self._log.info('No one home; not allowing switch to activate')

        self.toggle(state='off')


class SleepTimer(BaseSwitch):
    """Define a feature to turn a switch off after an amount of time."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.timer_changed,
            self.entity_ids['timer_slider'],
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_state(
            self.switch_turned_off,
            self.entity_ids['switch'],
            new='off',
            constrain_input_boolean=self.enabled_entity_id)

    def switch_turned_off(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Reset the sleep timer when the switch turns off."""
        self.set_value(self.entity_ids['timer_slider'], 0)

    def timer_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Start/stop a sleep timer for this switch."""
        minutes = int(float(new))

        if minutes == 0:
            self._log.info('Deactivating sleep timer')

            self.toggle(state='off')
            handle = self.handles.pop(HANDLE_TIMER)
            self.cancel_timer(handle)
        else:
            self._log.info('Activating sleep timer: %s minutes', minutes)

            self.toggle(state='on')
            self.handles[HANDLE_TIMER] = self.run_in(
                self.timer_completed, minutes * 60)

    def timer_completed(self, kwargs: dict) -> None:
        """Turn off a switch at the end of sleep timer."""
        self._log.info('Sleep timer over; turning switch off')

        self.set_value(self.entity_ids['timer_slider'], 0)


class ToggleAtTime(BaseSwitch):
    """Define a feature to toggle a switch at a certain time."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        kwargs = {
            'state': self.properties['state'],
            'constrain_input_boolean': self.enabled_entity_id
        }

        if self.properties.get('offset'):
            kwargs['offset'] = self.properties['offset']
        if self.properties.get('presence_required'):
            kwargs['constrain_anyone'] = 'home,just_arrived'

        if self.properties['schedule_time'] in ('sunrise', 'sunset'):
            method = getattr(
                self, 'run_at_{0}'.format(self.properties['schedule_time']))
            method(self.toggle_on_schedule, **kwargs)
        else:
            if self.properties.get('run_on_days'):
                run_on_days(
                    self, self.toggle_on_schedule,
                    self.properties['run_on_days'],
                    self.parse_time(self.properties['schedule_time']),
                    **kwargs)
            else:
                self.run_daily(
                    self.toggle_on_schedule,
                    self.parse_time(self.properties['schedule_time']),
                    **kwargs)


class ToggleOnInterval(BaseSwitch):
    """Define a feature to toggle the switch at intervals."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.run_daily(
            self.start_cycle,
            self.parse_time(self.properties['start_time']),
            constrain_input_boolean=self.enabled_entity_id)

        self.run_daily(
            self.stop_cycle,
            self.parse_time(self.properties['end_time']),
            constrain_input_boolean=self.enabled_entity_id)

        if (self.now_is_between(self.properties['start_time'],
                                self.properties['end_time'])
                and self.get_state(self.enabled_entity_id) == 'on'):
            self.start_cycle({})

    def start_cycle(self, kwargs: dict) -> None:
        """Start the toggle cycle."""
        self.handles[HANDLE_TOGGLE_IN_WINDOW] = self.run_every(
            self.toggle_on_schedule,
            self.datetime(),
            self.properties['window'],
            state=self.properties['state'])
        self.handles[HANDLE_TOGGLE_OUT_WINDOW] = self.run_every(
            self.toggle_on_schedule,
            self.datetime() + timedelta(seconds=self.properties['interval']),
            self.properties['window'],
            state=self.properties['state'],
            opposite=True)

    def stop_cycle(self, kwargs: dict) -> None:
        """Stop the toggle cycle."""
        self.toggle(opposite_of=self.properties['state'])

        for handle in (HANDLE_TOGGLE_IN_WINDOW, HANDLE_TOGGLE_OUT_WINDOW):
            name = self.handles.pop(handle)
            self.cancel_timer(name)


class ToggleOnState(BaseSwitch):
    """Define a feature to toggle the switch when an entity enters a state."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.attach_constraints(self.listen_for_state_change)

    def listen_for_state_change(self, constraints: dict = None) -> None:
        """Create a state listener for the target."""
        if not constraints:
            constraints = {}

        self.listen_state(
            self.state_changed,
            self.entity_ids['target'],
            constrain_input_boolean=self.enabled_entity_id,
            **constraints)

    def state_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Toggle the switch depending on the target entity's state."""
        if new == self.properties['target_state']:
            if self.properties.get('delay'):
                self.handles[HANDLE_TOGGLE_STATE] = self.run_in(
                    self.toggle_on_schedule,
                    self.properties['delay'],
                    state=self.properties['switch_state'])
            else:
                self.toggle(state=self.properties['switch_state'])
        else:
            if HANDLE_TOGGLE_STATE in self.handles:
                handle = self.handles.pop(HANDLE_TOGGLE_STATE)
                self.cancel_timer(handle)


class TurnOnUponArrival(BaseSwitch):
    """Define a feature to turn a switch on when one of us arrives."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.attach_constraints(self.listen_for_arrival)

    def listen_for_arrival(self, constraints: dict = None) -> None:
        """Create an event listener for someone arriving."""
        if not constraints:
            constraints = {}
        if self.properties.get('trigger_on_first_only'):
            constraints['first'] = True

        self.listen_event(
            self.someone_arrived,
            'PRESENCE_CHANGE',
            new=self.presence_manager.HomeStates.just_arrived.value,
            constrain_input_boolean=self.enabled_entity_id,
            **constraints)

    def someone_arrived(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on after dark when someone comes homes."""
        self._log.info('Someone came home; turning on the switch')

        self.toggle(state='on')


class TurnOnWhenCloudy(BaseSwitch):
    """Define a feature to turn a switch on at certain cloud coverage."""

    def initialize(self) -> None:
        """Initialize."""
        self.cloudy = False

        self.listen_state(
            self.cloud_coverage_reached,
            self.entity_ids['cloud_cover'],
            constrain_start_time=BLACKOUT_END,
            constrain_end_time=BLACKOUT_START,
            constrain_input_boolean=self.enabled_entity_id,
            constrain_anyone='just_arrived,home'
            if self.properties.get('presence_required') else None)

    def cloud_coverage_reached(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Turn on the switch when a "cloudy event" occurs."""
        try:
            cloud_cover = float(new)
        except ValueError:
            cloud_cover = 0.0

        if (not self.cloudy and cloud_cover >= THRESHOLD_CLOUDY):
            self._log.info('Cloud cover above %s%', cloud_cover)

            self.toggle(state='on')
            self.cloudy = True
        elif (self.cloudy and cloud_cover < THRESHOLD_CLOUDY):
            self._log.info('Cloud cover below %s%', cloud_cover)

            self.toggle(state='off')
            self.cloudy = False


class VacationMode(BaseSwitch):
    """Define a feature to simulate craziness when we're out of town."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.set_schedule(self.properties['start_time'], self.start_cycle)
        self.set_schedule(self.properties['end_time'], self.stop_cycle)

    def set_schedule(self, time: str, handler: Callable) -> None:
        """Set the appropriate schedulers based on the passed in time."""
        if time in ('sunrise', 'sunset'):
            method = getattr(self, 'run_at_{0}'.format(time))
            method(
                handler,
                constrain_input_boolean=self.enabled_entity_id)
        else:
            self.run_daily(
                handler,
                self.parse_time(time),
                constrain_input_boolean=self.enabled_entity_id)

    def start_cycle(self, kwargs: dict) -> None:
        """Start the toggle cycle."""
        self.toggle_and_run({'state': 'on'})

    def stop_cycle(self, kwargs: dict) -> None:
        """Stop the toggle cycle."""
        if HANDLE_VACATION_MODE not in self.handles:
            return

        handle = self.handles.pop(HANDLE_VACATION_MODE)
        self.cancel_timer(handle)

    def toggle_and_run(self, kwargs: dict) -> None:
        """Toggle the swtich and randomize the next toggle."""
        self.toggle(state=kwargs['state'])

        if kwargs['state'] == 'on':
            state = 'off'
        else:
            state = 'on'

        self.handles[HANDLE_VACATION_MODE] = self.run_in(
            self.toggle_and_run, randint(15 * 60, 45 * 60), state=state)
