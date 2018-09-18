"""Define automations for washer/dryer appliances."""

# pylint: disable=unused-argument

from datetime import timedelta
from enum import Enum
from typing import Union

from automation import Automation, Base  # type: ignore

HANDLE_CLEAN = 'clean'


class NotifyDone(Automation):
    """Define a feature to notify a target when the appliancer is done."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_ios_event(
            self.response_from_push_notification,
            self.properties['ios_emptied_key'])
        self.listen_state(
            self.power_changed,
            self.app.entities['power'],
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_state(
            self.status_changed,
            self.app.entities['status'],
            constrain_input_boolean=self.enabled_entity_id)

    def power_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Deal with changes to the power draw."""
        power = float(new)
        if (self.app.state != self.app.States.running
                and power >= self.properties['running_threshold']):
            self.log('Setting dishwasher to "Running"')

            self.app.state = (self.app.States.running)
        elif (self.app.state == self.app.States.running
              and power <= self.properties['drying_threshold']):
            self.log('Setting dishwasher to "Drying"')

            self.app.state = (self.app.States.drying)
        elif (self.app.state == self.app.States.drying
              and power == self.properties['clean_threshold']):
            self.log('Setting dishwasher to "Clean"')

            self.app.state = (self.app.States.clean)

    def status_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Deal with changes to the status."""
        if new == self.app.States.clean.value:
            self.handles[HANDLE_CLEAN] = self.notification_manager.repeat(
                'Dishwasher Clean 🍽',
                "Empty it now and you won't have to do it later!",
                self.properties['notification_interval'],
                when=self.datetime() + timedelta(minutes=15),
                target='home',
                data={'push': {
                    'category': 'dishwasher'
                }})
        elif old == self.app.States.clean.value:
            if HANDLE_CLEAN in self.handles:
                self.handles.pop(HANDLE_CLEAN)()

    def response_from_push_notification(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to iOS notification to empty the appliance."""
        self.log('Responding to iOS request that dishwasher is empty')

        self.app.state = self.app.States.dirty

        target = self.notification_manager.get_target_from_push_id(
            data['sourceDevicePermanentID'])
        self.notification_manager.send(
            'Dishwasher Emptied',
            '{0} emptied the dishwasher.'.format(target),
            target='not {0}'.format(target))


class WasherDryer(Base):
    """Define an app to represent a washer/dryer-type appliance."""

    class States(Enum):
        """Define an enum for states."""

        clean = 'Clean'
        dirty = 'Dirty'
        drying = 'Drying'
        running = 'Running'

    @property
    def state(self) -> Enum:
        """Get the state."""
        return self.States(self.get_state(self.entities['status']))

    @state.setter
    def state(self, value: Enum) -> None:
        """Set the state."""
        self.select_option(self.entities['status'], value.value)
