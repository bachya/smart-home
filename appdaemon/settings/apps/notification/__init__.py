"""Define the ability to send single and repeating notifications."""
# pylint: disable=too-few-public-methods
from datetime import datetime
from typing import Callable, List, Optional, Union
from uuid import uuid4

import attr

from core import Base
from helpers.dt import get_next_blackout_end, in_blackout
from notification.target import Target, get_targets_from_string

CONF_NOTIFICATION_HANDLES = 'notification_handles'


@attr.s(slots=True, auto_attribs=True)
class Notification:
    """Define a base notification object."""

    # App reference:
    _app: Base

    # Raw targets, message, and optional title:
    targets: Union[str, List[str]]
    message: str
    title: Optional[str] = None

    # Scheduling properties:
    urgent: bool = False
    repeat: bool = False
    when: Optional[datetime] = None
    interval: Optional[int] = None

    iterations: Optional[int] = None
    _iteration_count: int = 0

    # Message data
    data: Optional[dict] = None

    # "Auto-generated" properties:
    id: str = attr.Factory(lambda: uuid4().hex)

    def __attrs_post_init__(self):
        """Perform some post-__init__ initialization."""
        # Initialize a shared data space for handlers:
        if CONF_NOTIFICATION_HANDLES not in self._app.global_vars:
            self._app.global_vars[CONF_NOTIFICATION_HANDLES] = {}

        # Give every notification a parameter that will allow it to be
        # threaded on iOS; this shouldn't hurt any non-iOS notifier:
        if not self.data:
            self.data = {}
        self.data.setdefault('push', {'thread-id': self.id})

    def _cancel(self) -> None:
        """Cancel the notification."""
        if self.id not in self._app.global_vars[CONF_NOTIFICATION_HANDLES]:
            return

        handle = self._app.global_vars[CONF_NOTIFICATION_HANDLES].pop(self.id)
        if handle:
            self._app.cancel_timer(handle)

    def _send_cb(self, kwargs: dict) -> None:
        """Send a single (immediate or scheduled) notification."""
        # If a non-urgent send is going to occur in the blackout, reschedule it
        # to when the blackout ends:
        if not self.urgent and in_blackout(self.when.time()):  # type: ignore
            self._cancel()
            self.when = get_next_blackout_end(self.when)
            self.send()
            return

        # If this is a repeating notification, it's already been sent once, and
        # we've exceeded our iterations, cancel right away:
        if self.iterations and self._iteration_count == self.iterations:
            self._cancel()
            return

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

            self._app.call_service(target.service_call, **target.payload)

            if self.iterations:
                self._iteration_count += 1

    def send(self) -> Callable:
        """Send the notification."""
        handle = None
        if self.when and self.interval:
            handle = self._app.run_every(
                self._send_cb, self.when, self.interval)
        elif self.when:
            handle = self._app.run_at(self._send_cb, self.when)
        else:
            self._send_cb({})

        self._app.global_vars[CONF_NOTIFICATION_HANDLES][self.id] = handle
        return self._cancel


def send_notification(
        app: Base,
        targets: List[str],
        message: str,
        title: str = None,
        urgent: bool = False,
        when: datetime = None,
        interval: int = None,
        iterations: int = None,
        data: dict = None) -> Callable:
    """Send/schedule a notification and return a method to cancel it."""
    notification = Notification(  # type: ignore
        app=app,
        targets=targets,
        message=message,
        title=title,
        urgent=urgent,
        when=when,
        interval=interval,
        iterations=iterations,
        data=data)
    return notification.send()
