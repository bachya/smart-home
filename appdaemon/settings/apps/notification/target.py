"""Define various notification target types."""
# pylint: disable=too-few-public-methods
from typing import Dict, List

from const import CONF_PEOPLE
from core import Base  # pylint: disable=no-name-in-module


class Target:
    """Define a target for generic notifications."""

    def __init__(self, notify_service: str) -> None:
        """Initialize."""
        self.payload = {}  # type: Dict[str, str]
        self.service_call = "notify/{0}".format(notify_service)


class SlackTarget(Target):
    """Define a target for Slack notifications."""

    def __init__(self, channel: str = None, mention: str = None) -> None:
        """Initialize."""
        super().__init__("slack")

        if channel:
            self.payload["target"] = "#{0}".format(channel)
        if mention:
            self.payload["message"] = "{0}: ".format(mention)


class TargetFactory:
    """Define an abstract factory."""

    def __init__(self, app: Base, target: str) -> None:
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
        name = self._target.split("person:")[1]

        try:
            person = next(
                (p for p in self._app.global_vars[CONF_PEOPLE] if p.first_name == name)
            )
        except StopIteration:
            self._app.error("Unknown person: {0}".format(self._target))
            return []

        targets = []  # type: List[Target]
        for target in person.notifiers:
            targets += get_targets_from_string(self._app, target)

        return targets


class PresenceFactory(TargetFactory):
    """Define a factory to build notification targets specific to presence."""

    def build(self) -> List[Target]:
        """Build notification target objects from a string representation."""
        presence = self._target.split(":")[1]
        presence_manager = self._app.get_app("presence_manager")

        try:
            presence_method = getattr(presence_manager, "whos_{0}".format(presence))
        except AttributeError:
            self._app.error("Unknown presence target: {0}".format(presence))
            return []

        targets = []  # type: List[Target]
        for person in presence_method():
            for target in person.notifiers:
                targets += get_targets_from_string(self._app, target)

        return targets


class SlackFactory(TargetFactory):
    """Define a factory to build Slack notification targets."""

    def build(self) -> List[SlackTarget]:
        """Build notification target objects from a string representation."""
        data = self._target.split(":")

        if len(data) == 1:
            return [SlackTarget(None, None)]

        splits = data[1].split("/")

        if len(splits) == 2:
            return [SlackTarget(splits[0], splits[1])]

        if "@" in splits[0]:
            return [SlackTarget(None, splits[0])]

        return [SlackTarget(splits[0], None)]


def get_targets_from_string(app: Base, target: str) -> List[Target]:
    """Return the appropriate factory for the passed target."""
    if target.startswith("person:"):
        factory = PersonFactory(app, target)
    elif target.startswith("presence:"):
        factory = PresenceFactory(app, target)  # type: ignore
    elif target.startswith("slac:"):
        factory = SlackFactory(app, target)  # type: ignore
    else:
        factory = NotifierFactory(app, target)  # type: ignore

    return factory.build()
