"""Define various notification target types."""
# pylint: disable=too-few-public-methods
from typing import Dict, List

from appdaemon.plugins.hass.hassapi import Hass  # type: ignore

from const import CONF_PEOPLE


class Target:
    """Define a target for generic notifications."""

    def __init__(self, notify_service: str) -> None:
        """Initialize."""
        self.payload = {}  # type: Dict[str, str]
        self.service_call = 'notify/{0}'.format(notify_service)


class SlackTarget(Target):
    """Define a target for Slack notifications."""

    def __init__(self, channel: str = None, mention: str = None) -> None:
        """Initialize."""
        super().__init__('slack')

        if channel:
            self.payload['target'] = '#{0}'.format(channel)
        if mention:
            self.payload['message'] = '{0}: '.format(mention)


class TargetFactory:
    """Define an abstract factory."""

    def __init__(self, app: Hass, target: str) -> None:
        """Initialization."""
        self._app = app
        self._target = target

    def build(self) -> List:
        """Build  notification target objects from a string representation."""
        raise NotImplementedError()


class NotifierFactory(TargetFactory):
    """Define a factory to build generic notification targets."""

    def build(self) -> List[Target]:
        """Build  notification target objects from a string representation."""
        return [Target(self._target)]


class PersonFactory(TargetFactory):
    """Define a factory to build notification targets specific to a person."""

    def build(self) -> List[Target]:
        """Build notification target objects from a string representation."""
        name = self._target.split('person:')[1]

        try:
            person = next((
                p for p in self._app.global_vars[CONF_PEOPLE]
                if p.first_name == name))
        except StopIteration:
            self._app.error('Unknown person: {0}'.format(self._target))
            return []

        targets = []  # type: List[Target]
        for target in person.notifiers:
            if 'person:' in target:
                self._app.error('Refusing recursive name: {0}'.format(target))
                continue
            targets += get_targets_from_string(self._app, target)

        print(targets)
        return targets


class SlackFactory(TargetFactory):
    """Define a factory to build Slack notification targets."""

    def build(self) -> List[SlackTarget]:
        """Build notification target objects from a string representation."""
        splits = self._target.split(':')[1].split('/')
        num = len(splits)

        channel = None
        mention = None
        if num == 2:
            channel = splits[0]
            mention = splits[1]
        elif num == 1:
            if '@' in splits[0]:
                mention = splits[0]
            else:
                channel = splits[0]

        return [SlackTarget(channel, mention)]


def get_targets_from_string(app: Hass, target: str) -> List[Target]:
    """Return the appropriate factory for the passed target."""
    if 'person:' in target:
        factory = PersonFactory(app, target)
    elif 'slack:' in target:
        factory = SlackFactory(app, target)  # type: ignore
    else:
        factory = NotifierFactory(app, target)  # type: ignore

    return factory.build()
