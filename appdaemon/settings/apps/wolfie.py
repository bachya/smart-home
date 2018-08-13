"""Define automations for robot vacuums."""

# pylint: disable=attribute-defined-outside-init,unused-argument

from enum import Enum
from typing import Union

from app import App  # type: ignore
from automation import Automation, Feature  # type: ignore
from util.scheduler import run_on_days  # type: ignore


class MonitorConsumables(Feature):
    """Define a feature to notify when a consumable gets low."""

    def initialize(self) -> None:
        """Initialize."""
        for consumable in self.properties['consumables']:
            self.hass.listen_state(
                self.consumable_changed,
                self.hass.manager_app.entities['vacuum'],
                attribute=consumable,
                constrain_input_boolean=self.constraint)

    def consumable_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Create a task when a consumable is getting low."""
        if int(new) < self.properties['consumable_threshold']:
            self.hass.log('Consumable is low: {0}'.format(attribute))

            self.hass.notification_manager.create_omnifocus_task(
                'Order a new Wolfie consumable: {0}'.format(attribute))


class ScheduledCycle(Feature):
    """Define a feature to run the vacuum on a schedule."""

    HANDLE_BIN = 'vacuum_bin'
    HANDLE_STUCK = 'vacuum_stuck'

    @property
    def active_days(self) -> list:
        """Get the days that the vacuuming schedule should run."""
        on_days = []
        for toggle in self.properties['schedule_switches']:
            state = self.hass.get_state(toggle, attribute='all')
            if state['state'] == 'on':
                on_days.append(state['attributes']['friendly_name'])

        return on_days

    def initialize(self) -> None:
        """Initialize."""
        self.initiated_by_app = False

        self._schedule_handle = None
        self.create_schedule()

        self.hass.listen_event(
            self.alarm_changed,
            'ALARM_CHANGE',
            constrain_input_boolean=self.constraint)
        self.hass.listen_event(
            self.start_by_switch,
            'VACUUM_START',
            constrain_input_boolean=self.constraint)
        self.listen_ios_event(
            self.response_from_push_notification,
            self.properties['ios_emptied_key'])
        self.hass.listen_state(
            self.all_done,
            self.hass.manager_app.entities['status'],
            old=self.hass.manager_app.States.returning_home.value,
            new=self.hass.manager_app.States.charging.value,
            constrain_input_boolean=self.constraint)
        self.hass.listen_state(
            self.bin_state_changed,
            self.hass.manager_app.entities['bin_state'],
            constrain_input_boolean=self.constraint)
        self.hass.listen_state(
            self.errored,
            self.hass.manager_app.entities['status'],
            new=self.hass.manager_app.States.charger_disconnected.value,
            constrain_input_boolean=self.constraint)
        self.hass.listen_state(
            self.error_cleared,
            self.hass.manager_app.entities['status'],
            old=self.hass.manager_app.States.charger_disconnected.value,
            constrain_input_boolean=self.constraint)
        self.hass.listen_state(
            self.errored,
            self.hass.manager_app.entities['status'],
            new=self.hass.manager_app.States.error.value,
            constrain_input_boolean=self.constraint)
        self.hass.listen_state(
            self.error_cleared,
            self.hass.manager_app.entities['status'],
            old=self.hass.manager_app.States.error.value,
            constrain_input_boolean=self.constraint)
        for toggle in self.properties['schedule_switches']:
            self.hass.listen_state(
                self.schedule_changed,
                toggle,
                constrain_input_boolean=self.constraint)

    def alarm_changed(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to 'ALARM_CHANGE' events."""
        state = self.hass.manager_app.States(
            self.hass.get_state(self.hass.manager_app.entities['status']))

        # Scenario 1: Vacuum is charging and is told to start:
        if ((self.initiated_by_app
             and state == self.hass.manager_app.States.charging)
                and data['state'] ==
                self.hass.security_system.AlarmStates.home.value):
            self.hass.log('Activating vacuum (post-security)')

            self.hass.turn_on(self.hass.manager_app.entities['vacuum'])

        # Scenario 2: Vacuum is running when alarm is set to "Away":
        elif (state == self.hass.manager_app.States.cleaning and data['state']
              == self.hass.security_system.AlarmStates.away.value):
            self.hass.log('Security mode is "Away"; pausing until "Home"')

            self.hass.call_service(
                'vacuum/start_pause',
                entity_id=self.hass.manager_app.entities['vacuum'])
            self.hass.security_system.state = (
                self.hass.security_system.AlarmStates.home)

        # Scenario 3: Vacuum is paused when alarm is set to "Home":
        elif (state == self.hass.manager_app.States.paused and data['state'] ==
              self.hass.security_system.AlarmStates.home.value):
            self.hass.log('Alarm in "Home"; resuming')

            self.hass.call_service(
                'vacuum/start_pause',
                entity_id=self.hass.manager_app.entities['vacuum'])

    def all_done(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Re-arm security (if needed) when done."""
        self.hass.log('Vacuuming cycle all done')

        if (self.hass.presence_manager.noone(
                self.hass.presence_manager.HomeStates.just_arrived,
                self.hass.presence_manager.HomeStates.home)):
            self.hass.log('Changing alarm state to "away"')

            self.hass.security_system.state = (
                self.hass.security_system.AlarmStates.away)

        self.hass.manager_app.bin_state = (
            self.hass.manager_app.BinStates.full)
        self.initiated_by_app = False

    def bin_state_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Listen for changes in bin status."""
        if new == self.hass.manager_app.BinStates.full.value:
            self.handles[
                self.HANDLE_BIN] = self.hass.notification_manager.repeat(
                    'Wolfie Full 🤖',
                    "Empty him now and you won't have to do it later!",
                    60 * 60,
                    target='home',
                    data={'push': {
                        'category': 'wolfie'
                    }})
        elif new == self.hass.manager_app.BinStates.empty.value:
            if self.HANDLE_BIN in self.handles:
                self.handles.pop(self.HANDLE_BIN)()

    def create_schedule(self) -> None:
        """Create the vacuuming schedule from the on booleans."""
        self.hass.cancel_timer(self._schedule_handle)

        self._schedule_handle = run_on_days(  # type: ignore
            self.hass,
            self.start_by_schedule,
            self.active_days,
            self.hass.parse_time(self.properties['schedule_time']),
            constrain_input_boolean=self.constraint)

    def error_cleared(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Clear the error when Wolfie is no longer stuck."""
        if self.HANDLE_STUCK in self.handles:
            self.handles.pop(self.HANDLE_STUCK)()

    def errored(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Brief when Wolfie's had an error."""
        self.handles[
            self.HANDLE_STUCK] = self.hass.notification_manager.repeat(
                'Wolfie Stuck 😢',
                "Help him get back on track or home.",
                60 * 5,
                target='home',
            )

    def response_from_push_notification(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to iOS notification to empty vacuum."""
        self.hass.log('Responding to iOS request that vacuum is empty')

        self.hass.manager_app.bin_state = (
            self.hass.manager_app.BinStates.empty)

        target = self.hass.notification_manager.get_target_from_push_id(
            data['sourceDevicePermanentID'])
        self.hass.notification_manager.send(
            'Vacuum Emptied',
            '{0} emptied the vacuum.'.format(target),
            target='not {0}'.format(target))

    def schedule_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Reload the schedule when one of the input booleans change."""
        self.create_schedule()

    def start_by_schedule(self, kwargs: dict) -> None:
        """Start cleaning via the schedule."""
        if not self.initiated_by_app:
            self.hass.manager_app.start()
            self.initiated_by_app = True

    def start_by_switch(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Start cleaning via the switch."""
        if not self.initiated_by_app:
            self.hass.manager_app.start()
            self.initiated_by_app = True


class Vacuum(App):
    """Define an app to represent a vacuum-type appliance."""

    @property
    def bin_state(self) -> Enum:
        """Define a property to get the bin state."""
        return self.BinStates(self.get_state(self.entities['bin_state']))

    @bin_state.setter
    def bin_state(self, value: Enum) -> None:
        """Set the bin state."""
        self.call_service(
            'input_select/select_option',
            entity_id=self.entities['bin_state'],
            option=value.value)

    class BinStates(Enum):
        """Define an enum for vacuum bin states."""

        empty = 'Empty'
        full = 'Full'

    class States(Enum):
        """Define an enum for vacuum states."""

        charger_disconnected = 'Charger disconnected'
        charging_problem = 'Charging problem'
        charging = 'Charging'
        cleaning = 'Cleaning'
        docking = 'Docking'
        error = 'Error'
        going_to_target = 'Going to target'
        idle = 'Idle'
        manual_mode = 'Manual mode'
        paused = 'Paused'
        remote_control_active = 'Remote control active'
        returning_home = 'Returning home'
        shutting_down = 'Shutting down'
        spot_cleaning = 'Spot cleaning'
        starting = 'Starting'
        updating = 'Updating'
        zoned_cleaning = 'Zoned cleaning'

    def start(self) -> None:
        """Start a cleaning cycle."""
        self.log('Starting vacuuming cycle')

        if self.security_system.state == self.security_system.AlarmStates.away:
            self.log('Changing alarm state to "Home"')

            self.security_system.state = self.security_system.AlarmStates.home
        else:
            self.log('Activating vacuum')

            self.turn_on(self.entities['vacuum'])


class VacuumAutomation(Automation):
    """Define a class to represent automations for vacuums."""
