"""Define automations for robot vacuums."""
from enum import Enum
from typing import Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import CONF_ENTITY_IDS, CONF_PROPERTIES
from helpers import config_validation as cv
from helpers.scheduler import run_on_days

CONF_BIN_STATE = 'bin_state'
CONF_CONSUMABLES = 'consumables'
CONF_CONSUMABLE_THRESHOLD = 'consumable_threshold'
CONF_IOS_EMPTIED_KEY = 'ios_emptied_key'
CONF_NOTIFICATION_INTERVAL_FULL = 'notification_interval_full'
CONF_NOTIFICATION_INTERVAL_STUCK = 'notification_interval_stuck'
CONF_SCHEDULE_SWITCHES = 'schedule_switches'
CONF_SCHEDULE_TIME = 'schedule_time'
CONF_STATUS = 'status'
CONF_VACUUM = 'vacuum'

HANDLE_BIN = 'vacuum_bin'
HANDLE_SCHEDULE = 'schedule'
HANDLE_STUCK = 'vacuum_stuck'


class MonitorConsumables(Base):
    """Define a feature to notify when a consumable gets low."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_CONSUMABLE_THRESHOLD): int,
            vol.Required(CONF_CONSUMABLES): cv.ensure_list,
        }, extra=vol.ALLOW_EXTRA),
    })

    def configure(self) -> None:
        """Configure."""
        for consumable in self.properties['consumables']:
            self.listen_state(
                self.consumable_changed,
                self.app.entity_ids['vacuum'],
                attribute=consumable,
                constrain_input_boolean=self.enabled_entity_id)

    def consumable_changed(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Create a task when a consumable is getting low."""
        if int(new) < self.properties['consumable_threshold']:
            self.log('Consumable is low: {0}'.format(attribute))

            self.notification_manager.create_omnifocus_task(
                'Order a new Wolfie consumable: {0}'.format(attribute))


class ScheduledCycle(Base):
    """Define a feature to run the vacuum on a schedule."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_IOS_EMPTIED_KEY): str,
            vol.Required(CONF_NOTIFICATION_INTERVAL_FULL): int,
            vol.Required(CONF_NOTIFICATION_INTERVAL_STUCK): int,
            vol.Required(CONF_SCHEDULE_SWITCHES): cv.ensure_list,
            vol.Required(CONF_SCHEDULE_TIME): str,
        }, extra=vol.ALLOW_EXTRA),
    })

    @property
    def active_days(self) -> list:
        """Get the days that the vacuuming schedule should run."""
        on_days = []
        for toggle in self.properties['schedule_switches']:
            state = self.get_state(toggle, attribute='all')
            if state['state'] == 'on':
                on_days.append(state['attributes']['friendly_name'])

        return on_days

    def configure(self) -> None:
        """Configure."""
        self.initiated_by_app = False
        self.create_schedule()

        self.listen_event(
            self.alarm_changed,
            'ALARM_CHANGE',
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_event(
            self.start_by_switch,
            'VACUUM_START',
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_ios_event(
            self.response_from_push_notification,
            self.properties['ios_emptied_key'])
        self.listen_state(
            self.all_done,
            self.app.entity_ids['status'],
            old=self.app.States.returning.value,
            new=self.app.States.docked.value,
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_state(
            self.bin_state_changed,
            self.app.entity_ids['bin_state'],
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_state(
            self.errored,
            self.app.entity_ids['status'],
            new=self.app.States.error.value,
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_state(
            self.error_cleared,
            self.app.entity_ids['status'],
            old=self.app.States.error.value,
            constrain_input_boolean=self.enabled_entity_id)
        for toggle in self.properties['schedule_switches']:
            self.listen_state(
                self.schedule_changed,
                toggle,
                constrain_input_boolean=self.enabled_entity_id)

    def alarm_changed(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to 'ALARM_CHANGE' events."""
        state = self.app.States(self.get_state(self.app.entity_ids['status']))

        # Scenario 1: Vacuum is charging and is told to start:
        if ((self.initiated_by_app and state == self.app.States.docked) and
                data['state'] == self.security_manager.AlarmStates.home.value):
            self.log('Activating vacuum (post-security)')

            self.turn_on(self.app.entity_ids['vacuum'])

        # Scenario 2: Vacuum is running when alarm is set to "Away":
        elif (state == self.app.States.cleaning and
              data['state'] == self.security_manager.AlarmStates.away.value):
            self.log('Security mode is "Away"; pausing until "Home"')

            self.call_service(
                'vacuum/start_pause', entity_id=self.app.entity_ids['vacuum'])
            self.security_manager.set_alarm(
                self.security_manager.AlarmStates.home)

        # Scenario 3: Vacuum is paused when alarm is set to "Home":
        elif (state == self.app.States.paused and
              data['state'] == self.security_manager.AlarmStates.home.value):
            self.log('Alarm in "Home"; resuming')

            self.call_service(
                'vacuum/start_pause', entity_id=self.app.entity_ids['vacuum'])

    def all_done(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Re-arm security (if needed) when done."""
        self.log('Vacuuming cycle all done')

        if self.presence_manager.noone(
                self.presence_manager.HomeStates.just_arrived,
                self.presence_manager.HomeStates.home):
            self.log('Changing alarm state to "away"')

            self.security_manager.set_alarm(
                self.security_manager.AlarmStates.away)

        self.app.bin_state = self.app.BinStates.full
        self.initiated_by_app = False

    def bin_state_changed(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Listen for changes in bin status."""
        if new == self.app.BinStates.full.value:
            self.handles[HANDLE_BIN] = self.notification_manager.repeat(
                "Empty him now and you won't have to do it later!",
                self.properties[CONF_NOTIFICATION_INTERVAL_FULL],
                title='Wolfie Full 🤖',
                target='home',
                data={'push': {
                    'category': 'wolfie'
                }})
        elif new == self.app.BinStates.empty.value:
            if HANDLE_BIN in self.handles:
                self.handles.pop(HANDLE_BIN)()  # type: ignore

    def create_schedule(self) -> None:
        """Create the vacuuming schedule from the on booleans."""
        if HANDLE_SCHEDULE in self.handles:
            for handle in self.handles.pop(HANDLE_SCHEDULE):
                self.cancel_timer(handle)

        self.handles[HANDLE_SCHEDULE] = run_on_days(  # type: ignore
            self,
            self.start_by_schedule,
            self.active_days,
            self.parse_time(self.properties['schedule_time']),
            constrain_input_boolean=self.enabled_entity_id)

    def error_cleared(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Clear the error when Wolfie is no longer stuck."""
        if HANDLE_STUCK in self.handles:
            self.handles.pop(HANDLE_STUCK)()  # type: ignore

    def errored(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Brief when Wolfie's had an error."""
        self.handles[HANDLE_STUCK] = self.notification_manager.repeat(
            "Help him get back on track or home.",
            self.properties['notification_interval_stuck'],
            title='Wolfie Stuck 😢',
            target='home',
        )

    def response_from_push_notification(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to iOS notification to empty vacuum."""
        self.app.bin_state = (self.app.BinStates.empty)

        target = self.notification_manager.get_target_from_push_id(
            data['sourceDevicePermanentID'])
        self.notification_manager.send(
            '{0} emptied the vacuum.'.format(target.first_name),
            title='Vacuum Emptied 🤖',
            target='not {0}'.format(target.first_name))

    def schedule_changed(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Reload the schedule when one of the input booleans change."""
        self.create_schedule()

    def start_by_schedule(self, kwargs: dict) -> None:
        """Start cleaning via the schedule."""
        if not self.initiated_by_app:
            self.app.start()
            self.initiated_by_app = True

    def start_by_switch(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Start cleaning via the switch."""
        if not self.initiated_by_app:
            self.app.start()
            self.initiated_by_app = True


class Vacuum(Base):
    """Define an app to represent a vacuum-type appliance."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_BIN_STATE): cv.entity_id,
            vol.Required(CONF_STATUS): cv.entity_id,
            vol.Required(CONF_VACUUM): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
    })

    @property
    def bin_state(self) -> Enum:
        """Define a property to get the bin state."""
        return self.BinStates(self.get_state(self.entity_ids['bin_state']))

    @bin_state.setter
    def bin_state(self, value: Enum) -> None:
        """Set the bin state."""
        self.select_option(self.entity_ids['bin_state'], value.value)

    class BinStates(Enum):
        """Define an enum for vacuum bin states."""

        empty = 'Empty'
        full = 'Full'

    class States(Enum):
        """Define an enum for vacuum states."""

        cleaning = 'Cleaning'
        docked = 'Docked'
        error = 'Error'
        idle = 'Idle'
        paused = 'Paused'
        remote_control = 'Remote Control'
        returning = 'Returning'

    def start(self) -> None:
        """Start a cleaning cycle."""
        self.log('Starting vacuuming cycle')

        if (self.security_manager.alarm_state ==
                self.security_manager.AlarmStates.away):
            self.log('Changing alarm state to "Home"')

            self.security_manager.set_alarm(
                self.security_manager.AlarmStates.home)
        else:
            self.log('Activating vacuum')

            self.call_service(
                'vacuum/start', entity_id=self.entity_ids['vacuum'])
