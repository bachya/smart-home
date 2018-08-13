"""Define automations for washer/dryer appliances."""

# pylint: disable=unused-argument

from datetime import timedelta
from enum import Enum
from typing import Union

from app import App  # type: ignore
from automation import Automation, Feature  # type: ignore


class WasherDryer(App):
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
        self.call_service(
            'input_select/select_option',
            entity_id=self.entities['status'],
            option=value.value)


class WasherDryerAutomation(Automation):
    """Define a class to represent automations for washer/dryer appliances."""


class NotifyDone(Feature):
    """Define a feature to notify a target when the appliancer is done."""

    HANDLE_CLEAN = 'clean'

    def initialize(self) -> None:
        """Initialize."""
        self.listen_ios_event(
            self.response_from_push_notification,
            self.properties['ios_emptied_key'])
        self.hass.listen_state(
            self.power_changed,
            self.hass.manager_app.entities['power'],
            constrain_input_boolean=self.constraint)
        self.hass.listen_state(
            self.status_changed,
            self.hass.manager_app.entities['status'],
            constrain_input_boolean=self.constraint)

    def power_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Deal with changes to the power draw."""
        power = float(new)
        if (self.hass.manager_app.state != self.hass.manager_app.States.running
                and power >= self.properties['running_threshold']):
            self.hass.log('Setting dishwasher to "Running"')

            self.hass.manager_app.state = (
                self.hass.manager_app.States.running)
        elif (self.hass.manager_app.state ==
              self.hass.manager_app.States.running
              and power <= self.properties['drying_threshold']):
            self.hass.log('Setting dishwasher to "Drying"')

            self.hass.manager_app.state = (self.hass.manager_app.States.drying)
        elif (self.hass.manager_app.state ==
              self.hass.manager_app.States.drying
              and power == self.properties['clean_threshold']):
            self.hass.log('Setting dishwasher to "Clean"')

            self.hass.manager_app.state = (self.hass.manager_app.States.clean)

    def status_changed(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Deal with changes to the status."""
        if new == self.hass.manager_app.States.clean.value:
            self.handles[
                self.HANDLE_CLEAN] = self.hass.notification_manager.repeat(
                    'Dishwasher Clean 🍽',
                    "Empty it now and you won't have to do it later!",
                    60 * 60,
                    when=self.hass.datetime() + timedelta(minutes=15),
                    target='home',
                    data={'push': {
                        'category': 'dishwasher'
                    }})
        elif old == self.hass.manager_app.States.clean.value:
            if self.HANDLE_CLEAN in self.handles:
                self.handles.pop(self.HANDLE_CLEAN)()

    def response_from_push_notification(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to iOS notification to empty the appliance."""
        self.hass.log('Responding to iOS request that dishwasher is empty')

        self.hass.manager_app.state = self.hass.manager_app.States.dirty

        target = self.hass.notification_manager.get_target_from_push_id(
            data['sourceDevicePermanentID'])
        self.hass.notification_manager.send(
            'Dishwasher Emptied',
            '{0} emptied the dishwasher.'.format(target),
            target='not {0}'.format(target))
