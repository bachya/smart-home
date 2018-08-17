"""Define automations for security."""

# pylint: disable=unused-argument

from datetime import time
from enum import Enum
from typing import Union

from app import App  # type: ignore
from automation import Automation, Feature  # type: ignore


class SecuritySystem(App):
    """Define a class to represent the app."""

    class AlarmStates(Enum):
        """Define an enum for alarm states."""

        away = 'armed_away'
        disarmed = 'disarmed'
        home = 'armed_home'

    ALARM_CONTROL_PANEL = 'alarm_control_panel.simplisafe'
    SECURE_STATUS_SENSOR = 'sensor.secure_status'

    IS_INSECURE_MAPPING = {
        'the door to the garage': {
            'entity': 'lock.garage_fire_door',
            'state': 'unlocked'
        },
        'the front door': {
            'entity': 'lock.front_door',
            'state': 'unlocked'
        },
        'the garage door': {
            'entity': 'cover.garage_door',
            'state': 'open'
        },
        'the security system': {
            'entity': 'alarm_control_panel.simplisafe',
            'state': 'disarmed'
        }
    }

    @property
    def secure(self) -> bool:
        """Return whether the house is secure or not."""
        return self.get_state('sensor.secure_status') == 'Secure'

    @property
    def state(self) -> Enum:
        """Return the current state of the security system."""
        return self.AlarmStates(self.get_state(self.ALARM_CONTROL_PANEL))

    @state.setter
    def state(self, new: Enum) -> None:
        """Return the security state."""
        if new == self.AlarmStates.disarmed:
            self.log('Disarming the security system')
            self.call_service(
                'alarm_control_panel/alarm_disarm',
                entity_id=self.ALARM_CONTROL_PANEL)
        elif new in (self.AlarmStates.away, self.AlarmStates.home):
            self.log('Arming the security system: "{0}"'.format(new.name))
            self.call_service(
                'alarm_control_panel/alarm_arm_{0}'.format(
                    new.value.split('_')[1]),
                entity_id=self.ALARM_CONTROL_PANEL)
        else:
            raise AttributeError("Can't set alarm to state: {0}".format(new))

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self._security_system_change_cb, self.ALARM_CONTROL_PANEL)

    def _security_system_change_cb(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Fire events when the security system status changes."""
        if new != 'unknown':
            self.fire_event('ALARM_CHANGE', state=new)

    def get_insecure_entities(self) -> list:
        """Return a list of insecure entities."""
        return [
            name for name, entity in self.IS_INSECURE_MAPPING.items()
            if self.get_state(entity['entity']) == entity['state']
        ]


class SecurityAutomation(Automation):
    """Define a class to represent automations for security."""


class AbsentInsecure(Feature):
    """Define a feature to notify us when we've left home insecure."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_event(
            self.response_from_push_notification,
            'ios.notification_action_fired',
            actionName='LOCK_UP_AWAY',
            constrain_input_boolean=self.enabled_toggle,
            action='away')
        self.hass.listen_event(
            self.response_from_push_notification,
            'ios.notification_action_fired',
            actionName='LOCK_UP_HOME',
            constrain_input_boolean=self.enabled_toggle,
            action='home')
        self.hass.listen_state(
            self.house_insecure,
            self.entities['state'],
            new='Open',
            duration=60 * 5,
            constrain_input_boolean=self.enabled_toggle,
            constrain_noone='just_arrived,home')

    def house_insecure(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send notifications when the house has been left insecure."""
        self.hass.log('No one home and house is insecure; notifying')

        self.hass.notification_manager.send(
            'Security Issue',
            "No one is home and the house isn't locked up.",
            blackout_start_time=None,
            blackout_end_time=None,
            data={'push': {
                'category': 'security'
            }})

    def response_from_push_notification(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to 'ios.notification_action_fired' events."""
        target = self.hass.notification_manager.get_target_from_push_id(
            data['sourceDevicePermanentID'])

        if kwargs['action'] == 'home':
            self.hass.log('Responding to iOS request to lock up home (home)')

            self.hass.turn_on('scene.good_night')
        elif kwargs['action'] == 'away':
            self.hass.log('Responding to iOS request to lock up home (away)')

            self.hass.turn_on('scene.depart_home')

        self.hass.notification_manager.send(
            'Issue Resolved',
            '{0} locked up the house.'.format(target),
            target='not {0}'.format(target))


class AutoDepartureLockup(Feature):
    """Define a feature to automatically lock up when we leave."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_event(
            self.everyone_gone,
            'PROXIMITY_CHANGE',
            constrain_input_boolean=self.enabled_toggle)

    def everyone_gone(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to 'PROXIMITY_CHANGE' events."""
        if (not self.hass.security_system.secure and data['old'] ==
                self.hass.presence_manager.ProximityStates.home.value
                and data['new'] !=
                self.hass.presence_manager.ProximityStates.home.value):
            self.hass.log('Everyone has left; locking up')

            self.hass.turn_on('scene.depart_home')


class AutoNighttimeLockup(Feature):
    """Define a feature to automatically lock up at night."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.run_daily(
            self.midnight,
            time(0, 0, 0),
            constrain_input_boolean=self.enabled_toggle,
            constrain_anyone='home')

    def midnight(self, kwargs: dict) -> None:
        """Lock up the house at midnight."""
        self.hass.log('Activating "Good Night"')

        self.hass.call_service('scene/turn_on', entity_id='scene.good_night')


class GarageLeftOpen(Feature):
    """Define a feature to notify us when the garage is left open."""

    HANDLE = 'garage_open'

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_event(
            self.response_from_push_notification,
            'ios.notification_action_fired',
            actionName='GARAGE_CLOSE',
            constrain_input_boolean=self.enabled_toggle)
        self.hass.listen_state(
            self.closed,
            self.entities['garage_door'],
            new='closed',
            constrain_input_boolean=self.enabled_toggle)
        self.hass.listen_state(
            self.left_open,
            self.entities['garage_door'],
            new='open',
            duration=60 * int(self.properties['time_left_open']),
            constrain_input_boolean=self.enabled_toggle)

    def closed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Cancel notification when the garage is closed."""
        if self.HANDLE in self.handles:
            self.handles.pop(self.HANDLE)()

    def left_open(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send notifications when the garage has been left open."""
        self.handles[self.HANDLE] = self.hass.notification_manager.repeat(
            'Garage Open 🚗',
            "The garage has been left open for a while.",
            60 * 60,
            blackout_start_time=None,
            blackout_end_time=None,
            data={'push': {
                'category': 'garage'
            }})

    def response_from_push_notification(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to 'ios.notification_action_fired' events."""
        target = self.hass.notification_manager.get_target_from_push_id(
            data['sourceDevicePermanentID'])

        self.hass.log('Responding to iOS request to close garage')

        self.hass.call_service(
            'cover/close_cover', entity_id=self.entities['garage_door'])

        self.hass.notification_manager.send(
            'Issue Resolved',
            '{0} closed the garage.'.format(target),
            target='not {0}'.format(target))


class NotifyOnChange(Feature):
    """Define a feature to notify us the secure status changes."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_state(
            self.state_changed,
            self.entities['state'],
            constrain_input_boolean=self.enabled_toggle)

    def state_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send a notification when the security state changes."""
        self.hass.log('Notifying of security status change: {0}'.format(new))

        self.hass.notification_manager.send(
            'Security Change',
            'The security status has changed to "{0}"'.format(new),
            blackout_start_time=None,
            blackout_end_time=None)
