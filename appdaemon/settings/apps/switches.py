"""Define automations for switches."""

# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Union

from automation import Automation, Feature  # type: ignore
from const import (  # type: ignore
    BLACKOUT_END, BLACKOUT_START, THRESHOLD_CLOUDY)
from util.scheduler import run_on_days  # type: ignore


class SwitchAutomation(Automation):
    """Define an automation for switches."""


class BaseFeature(Feature):
    """Define a base feature for all switches."""

    @property
    def state(self) -> bool:
        """Return the current state of the switch."""
        return self.hass.get_state(self.entities['switch'])

    def initialize(self) -> None:
        """Initialize."""
        raise NotImplementedError

    def toggle(self, state: str) -> None:
        """Toggle the switch state."""
        if self.state == 'off' and state == 'on':
            self.hass.log('Turning on: {0}'.format(self.entities['switch']))
            self.hass.turn_on(self.entities['switch'])
        elif self.state == 'on' and state == 'off':
            self.hass.log('Turning off: {0}'.format(self.entities['switch']))
            self.hass.turn_off(self.entities['switch'])

    def toggle_on_schedule(self, kwargs: dict) -> None:
        """Turn off the switch at a certain time."""
        self.toggle(kwargs['state'])


class PresenceFailsafe(BaseFeature):
    """Define a feature to restrict activation when we're not home."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_state(
            self.switch_activated,
            self.entities['switch'],
            new='on',
            constrain_noone='just_arrived,home',
            constrain_input_boolean=self.enabled_toggle)

    def switch_activated(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Turn the switch off if no one is home."""
        self.hass.log('No one home; not allowing switch to activate')
        self.toggle('off')


class SleepTimer(BaseFeature):
    """Define a feature to turn a switch off after an amount of time."""

    def initialize(self) -> None:
        """Initialize."""
        self._handle = None

        self.hass.listen_state(
            self.timer_changed,
            self.entities['timer_slider'],
            constrain_input_boolean=self.enabled_toggle)
        self.hass.listen_state(
            self.switch_turned_off,
            self.entities['switch'],
            new='off',
            constrain_input_boolean=self.enabled_toggle)

    def switch_turned_off(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Reset the sleep timer when the switch turns off."""
        self.hass.call_service(
            'input_number/set_value',
            entity_id=self.entities['timer_slider'],
            value=0)

    def timer_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Start/stop a sleep timer for this switch."""
        minutes = int(float(new))

        if minutes == 0:
            self.hass.log('Deactivating sleep timer')

            self.toggle('off')
            self.hass.cancel_timer(self._handle)
        else:
            self.hass.log(
                'Activating sleep timer: {0} minutes'.format(minutes))

            self.toggle('on')
            self._handle = self.hass.run_in(self.timer_completed, minutes * 60)

    def timer_completed(self, kwargs: dict) -> None:
        """Turn off a switch at the end of sleep timer."""
        self.hass.log('Sleep timer over; turning switch off')

        self.hass.call_service(
            'input_number/set_value',
            entity_id=self.entities['timer_slider'],
            value=0)


class ToggleAtTime(BaseFeature):
    """Define a feature to toggle a switch at a certain time."""

    @property
    def repeatable(self) -> bool:
        """Define whether a feature can be implemented multiple times."""
        return True

    def initialize(self) -> None:
        """Initialize."""
        if self.properties['schedule_time'] in ['sunrise', 'sunset']:
            method = getattr(
                self.hass, 'run_at_{0}'.format(
                    self.properties['schedule_time']))
            method(
                self.toggle_on_schedule,
                state=self.properties['state'],
                offset=self.properties.get('seasonal_offset', False),
                constrain_input_boolean=self.enabled_toggle,
                constrain_anyone='just_arrived,home'
                if self.properties.get('presence_required') else None)
        else:
            if self.properties.get('run_on_days'):
                run_on_days(
                    self.hass,
                    self.toggle_on_schedule,
                    self.properties['run_on_days'],
                    self.hass.parse_time(self.properties['schedule_time']),
                    state=self.properties['state'],
                    constrain_input_boolean=self.enabled_toggle)
            else:
                self.hass.run_daily(
                    self.toggle_on_schedule,
                    self.hass.parse_time(self.properties['schedule_time']),
                    state=self.properties['state'],
                    constrain_input_boolean=self.enabled_toggle)


class ToggleIfToggled(BaseFeature):
    """Define a feature to immediately toggle a switch back."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_state(
            self.switch_toggled,
            self.entities['switch'],
            old=self.properties['desired_state'],
            constrain_input_boolean=self.enabled_toggle)

    def delay_complete(self, kwargs: dict) -> None:
        """Toggle the switch back after a delay."""
        self.toggle(self.properties['desired_state'])

    def switch_toggled(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Toggle the switch back."""
        if self.properties.get('delay'):
            self.hass.run_in(self.delay_complete, self.properties['delay'])
        else:
            self.toggle(self.properties['desired_state'])


class TurnOnUponArrival(BaseFeature):
    """Define a feature to turn a switch on when one of us arrives."""

    def initialize(self) -> None:
        """Initialize."""
        if self.properties.get('possible_conditions'):
            for name, value in self.properties['possible_conditions'].items():
                self.listen_for_arrival({name: value})
        else:
            self.listen_for_arrival()

    def listen_for_arrival(self, constraint_kwargs: dict = None) -> None:
        """Create an event listen for someone arriving."""
        if not constraint_kwargs:
            constraint_kwargs = {}
        if self.properties.get('trigger_on_first_only'):
            constraint_kwargs['first'] = True

        self.hass.listen_event(
            self.someone_arrived,
            'PRESENCE_CHANGE',
            new=self.hass.presence_manager.HomeStates.just_arrived.value,
            constrain_input_boolean=self.enabled_toggle,
            **constraint_kwargs)

    def someone_arrived(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on after dark when someone comes homes."""
        self.hass.log('Someone came home after dark; turning on the switch')

        self.toggle('on')


class TurnOnWhenCloudy(BaseFeature):
    """Define a feature to turn a switch on at certain cloud coverage."""

    def initialize(self) -> None:
        """Initialize."""
        self.cloudy = False

        self.hass.listen_state(
            self.cloud_coverage_reached,
            self.entities['cloud_cover'],
            constrain_start_time=BLACKOUT_END,
            constrain_end_time=BLACKOUT_START,
            constrain_input_boolean=self.enabled_toggle,
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
            self.hass.log('Cloud cover above {0}%'.format(cloud_cover))

            self.toggle('on')
            self.cloudy = True
        elif (self.cloudy and cloud_cover < THRESHOLD_CLOUDY):
            self.hass.log('Cloud cover below {0}%'.format(cloud_cover))

            self.toggle('off')
            self.cloudy = False


class VacationMode(BaseFeature):
    """Define a feature to simulate craziness when we're out of town."""

    def initialize(self) -> None:
        """Initialize."""
        self._off_handle = None
        self._on_handle = None

        self.hass.listen_event(
            self.vacation_mode_toggled, 'MODE_CHANGE', mode='vacation_mode')

    def vacation_mode_toggled(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to changes when vacation mode gets toggled."""
        if data['state'] == 'on':
            self._on_handler = self.hass.run_at_sunset(
                self.toggle_on_schedule,
                state='on',
                random_start=-60 * 60 * 1,
                random_end=60 * 30 * 1)
            self._off_handler = self.hass.run_at_sunset(
                self.toggle_on_schedule,
                state='off',
                random_start=60 * 60 * 2,
                random_end=60 * 60 * 4)
        else:
            self.hass.cancel_timer(self._off_handle)
            self.hass.cancel_timer(self._on_handle)
