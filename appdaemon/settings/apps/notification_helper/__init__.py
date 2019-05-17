"""Define the ability to send single and repeating notifications."""
# pylint: disable=too-few-public-methods
import datetime
from typing import List, Optional, Union
from uuid import uuid4

from appdaemon.plugins.hass.hassapi import Hass  # type: ignore
import attr

from target import Target, get_targets_from_string


@attr.s(slots=True, auto_attribs=True)
class Notification:
    """Define a base notification object."""

    # App reference:
    _app: Hass

    # Raw targets, message, and optional title:
    targets: Union[str, List[str]]
    message: str
    title: Optional[str] = None

    # Scheduling properties:
    repeat: bool = False
    when: Optional[datetime.datetime] = None
    interval: Optional[int] = None
    blackout_start_time: Optional[datetime.datetime] = None
    blackout_end_time: Optional[datetime.datetime] = None

    # "Auto-generated" properties:
    id: str = attr.Factory(lambda: uuid4().hex)
    data: dict = attr.Factory(dict)

    def __attrs_post_init__(self):
        """Perform some post-__init__ initialization."""
        if not self.data:
            self.data = {}
        self.data.setdefault('push', {'thread-id': self.id})

    def send(self) -> None:
        """Send the notification."""
        if isinstance(self.targets, str):
            self.targets = [self.targets]

        targets = []  # type: List[Target]
        for target_str in self.targets:
            targets += get_targets_from_string(self._app, target_str)

        for target in targets:
            target.payload['data'] = self.data
            if self.title:
                target.payload['title'] = self.title
            if target.payload.get('message'):
                target.payload['message'] += self.message
            else:
                target.payload['message'] = self.message

            self._app.log('Sending message: {0}'.format(self))

            self._app.call_service(target.service_call, **target.payload)


def send_notification(
        app: Hass, targets: List[str], message: str,
        **kwargs: dict) -> Notification:
    """Send/schedule a notification and return its ID."""
    notification = Notification(  # type: ignore
        app=app, targets=targets, message=message, **kwargs)
    notification.send()
    return notification
