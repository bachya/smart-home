"""Define automations for switches."""

# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Callable, Union

from automation import Automation  # type: ignore
from const import (  # type: ignore
    BLACKOUT_END, BLACKOUT_START, THRESHOLD_CLOUDY)
from util.scheduler import run_on_days  # type: ignore

HANDLE_TIMER = 'timer'
HANDLE_TOGGLE_STATE = 'toggle_state'
HANDLE_VACATION_MODE_OFF = 'vacation_mode_off'
HANDLE_VACATION_MODE_ON = 'vacation_mode_on'


class BaseSwitch(Automation):
    """Define a base feature for all switches."""

    @property
    def state(self) -> bool:
        """Return the current state of the switch."""
        return self.get_state(self.entities['switch'])

    def attach_constraints(self, func: Callable) -> None:
        """Attach values from possible_constraints to a function."""
        if self.properties.get('possible_constraints'):
            for name, value in self.properties['possible_constraints'].items():
                func({name: value})
        else:
            func()

    def toggle(self, state: str) -> None:
        """Toggle the switch state."""
        if self.state == 'off' and state == 'on':
            self.log('Turning on: {0}'.format(self.entities['switch']))
            self.turn_on(self.entities['switch'])
        elif self.state == 'on' and state == 'off':
            self.log('Turning off: {0}'.format(self.entities['switch']))
            self.turn_off(self.entities['switch'])

    def toggle_on_schedule(self, kwargs: dict) -> None:
        """Turn off the switch at a certain time."""
        self.toggle(kwargs['state'])


class BaseZwaveSwitch(BaseSwitch):
    """Define a Zwave switch."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_event(
            self.double_up,
            'zwave.node_event',
            entity_id=self.entities['zwave_device'],
            basic_level=255,
            constrain_input_boolean=self.enabled_entity_id)

        self.listen_event(
            self.double_down,
            'zwave.node_event',
            entity_id=self.entities['zwave_device'],
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

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.switch_turned_off,
            self.entities['switch'],
            new='off',
            constrain_input_boolean=self.enabled_entity_id)

    def double_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on the target switch with a double up tap."""
        self.log(
            'Starting {0}-second time for switch'.format(
                self.properties['duration']))

        self.toggle('on')
        self.handles[HANDLE_TIMER] = self.run_in(
            self.timer_completed, self.properties['duration'])

    def switch_turned_off(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Cancel any timer if the switch is turned off."""
        if HANDLE_TIMER in self.handles:
            handle = self.handles.pop(HANDLE_TIMER)
            self.cancel_timer(handle)

    def timer_completed(self, kwargs: dict) -> None:
        """Turn off a switch at the end of the timer."""
        self.log('Double-tapped timer over; turning switch off')

        self.toggle('off')
        self.handles.pop(HANDLE_TIMER, None)


class DoubleTapToggleSwitch(BaseZwaveSwitch):
    """Define a feature to toggle a switch with a double tab of this switch."""

    def double_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn off the target switch with a double down tap."""
        self.turn_off(self.entities['target'])

    def double_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on the target switch with a double up tap."""
        self.turn_on(self.entities['target'])


class PresenceFailsafe(BaseSwitch):
    """Define a feature to restrict activation when we're not home."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.switch_activated,
            self.entities['switch'],
            new='on',
            constrain_noone='just_arrived,home',
            constrain_input_boolean=self.enabled_entity_id)

    def switch_activated(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Turn the switch off if no one is home."""
        self.log('No one home; not allowing switch to activate')

        self.toggle('off')


class SleepTimer(BaseSwitch):
    """Define a feature to turn a switch off after an amount of time."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.timer_changed,
            self.entities['timer_slider'],
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_state(
            self.switch_turned_off,
            self.entities['switch'],
            new='off',
            constrain_input_boolean=self.enabled_entity_id)

    def switch_turned_off(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Reset the sleep timer when the switch turns off."""
        self.set_value(self.entities['timer_slider'], 0)

    def timer_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Start/stop a sleep timer for this switch."""
        minutes = int(float(new))

        if minutes == 0:
            self.log('Deactivating sleep timer')

            self.toggle('off')
            handle = self.handles.pop(HANDLE_TIMER)
            self.cancel_timer(handle)
        else:
            self.log('Activating sleep timer: {0} minutes'.format(minutes))

            self.toggle('on')
            self.handles[HANDLE_TIMER] = self.run_in(
                self.timer_completed, minutes * 60)

    def timer_completed(self, kwargs: dict) -> None:
        """Turn off a switch at the end of sleep timer."""
        self.log('Sleep timer over; turning switch off')

        self.set_value(self.entities['timer_slider'], 0)


class ToggleAtTime(BaseSwitch):
    """Define a feature to toggle a switch at a certain time."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        if self.properties['schedule_time'] in ['sunrise', 'sunset']:
            method = getattr(
                self, 'run_at_{0}'.format(self.properties['schedule_time']))
            method(
                self.toggle_on_schedule,
                state=self.properties['state'],
                offset=self.properties.get('seasonal_offset', False),
                constrain_input_boolean=self.enabled_entity_id,
                constrain_anyone='just_arrived,home'
                if self.properties.get('presence_required') else None)
        else:
            if self.properties.get('run_on_days'):
                run_on_days(
                    self,
                    self.toggle_on_schedule,
                    self.properties['run_on_days'],
                    self.parse_time(self.properties['schedule_time']),
                    state=self.properties['state'],
                    constrain_input_boolean=self.enabled_entity_id)
            else:
                self.run_daily(
                    self.toggle_on_schedule,
                    self.parse_time(self.properties['schedule_time']),
                    state=self.properties['state'],
                    constrain_input_boolean=self.enabled_entity_id)


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
            self.entities['target'],
            constrain_input_boolean=self.enabled_entity_id,
            **constraints)

    def state_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Toggle the switch depending on the target entity's state."""
        if new == self.properties['trigger_state']:
            if self.properties.get('delay'):
                self.handles[HANDLE_TOGGLE_STATE] = self.run_in(
                    self.toggle_on_schedule,
                    self.properties['delay'],
                    state=self.properties['switch_state'])
            else:
                self.toggle(self.properties['switch_state'])
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
        self.log('Someone came home; turning on the switch')

        self.toggle('on')


class TurnOnWhenCloudy(BaseSwitch):
    """Define a feature to turn a switch on at certain cloud coverage."""

    def initialize(self) -> None:
        """Initialize."""
        self.cloudy = False

        self.listen_state(
            self.cloud_coverage_reached,
            self.entities['cloud_cover'],
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
            self.log('Cloud cover above {0}%'.format(cloud_cover))

            self.toggle('on')
            self.cloudy = True
        elif (self.cloudy and cloud_cover < THRESHOLD_CLOUDY):
            self.log('Cloud cover below {0}%'.format(cloud_cover))

            self.toggle('off')
            self.cloudy = False


class VacationMode(BaseSwitch):
    """Define a feature to simulate craziness when we're out of town."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_event(
            self.vacation_mode_toggled, 'MODE_CHANGE', mode='vacation_mode')

    def vacation_mode_toggled(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to changes when vacation mode gets toggled."""
        if data['state'] == 'on':
            self.handles[HANDLE_VACATION_MODE_ON] = self.run_at_sunset(
                self.toggle_on_schedule,
                state='on',
                random_start=-60 * 60 * 1,
                random_end=60 * 30 * 1)
            self.handles[HANDLE_VACATION_MODE_OFF] = self.run_at_sunset(
                self.toggle_on_schedule,
                state='off',
                random_start=60 * 60 * 2,
                random_end=60 * 60 * 4)
        else:
            for key in (HANDLE_VACATION_MODE_OFF, HANDLE_VACATION_MODE_ON):
                handle = self.handles.pop(key)
                self.cancel_timer(handle)
