"""Define the ability to send single and repeating notifications."""
# pylint: disable=too-few-public-methods
from datetime import datetime
from typing import Callable, List, Optional, Union
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
    when: Optional[datetime] = None
    interval: Optional[int] = None
    blackout_start_time: Optional[datetime] = None
    blackout_end_time: Optional[datetime] = None

    # "Auto-generated" properties:
    id: str = attr.Factory(lambda: uuid4().hex)
    data: dict = attr.Factory(dict)

    def __attrs_post_init__(self):
        """Perform some post-__init__ initialization."""
        # Give every notification a parameter that will allow it to be
        # threaded on iOS; this shouldn't hurt any non-iOS notifier:
        if not self.data:
            self.data = {}
        self.data.setdefault('push', {'thread-id': self.id})

    def _log(self, message: str) -> None:
        """Log a message and include the notification's info."""
        self._app.log('{0} <{1}>'.format(message, self))

    def _send_cb(self, kwargs: dict) -> None:
        """Send a single (immediate or scheduled) notification."""
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

            self._log('Sending notification')
            self._app.call_service(target.service_call, **target.payload)

    def send(self) -> Callable:
        """Send the notification."""
        if self.when:
            self._log('Scheduling notification')
            handle = self._app.run_at(self._send_cb, self.when)
        else:
            self._send_cb({})

        def cancel():
            """Define a method to cancel the notification."""
            if self.when:
                self._log('Canceling notification')
                self._app.cancel_timer(handle)

        return cancel


def send_notification(
        app: Hass, targets: List[str], message: str,
        **kwargs: dict) -> Callable:
    """Send/schedule a notification and return its ID."""
    notification = Notification(  # type: ignore
        app=app, targets=targets, message=message, **kwargs)
    return notification.send()
