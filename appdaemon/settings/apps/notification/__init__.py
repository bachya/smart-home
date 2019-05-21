"""Define the ability to send single and repeating notifications."""
# pylint: disable=too-few-public-methods
from datetime import datetime, time
from typing import Callable, List, Optional, Union
from uuid import uuid4

import attr

from core import Base
from notification.target import Target, get_targets_from_string


@attr.s(slots=True, auto_attribs=True)
class Notification:
    """Define a base notification object."""

    # App reference:
    _app: Base

    # Raw targets, message, and optional title:
    targets: Union[str, List[str]]
    message: str
    title: Optional[str] = None

    # Cancellation method:
    _cancel_method: Optional[Callable] = None

    # Scheduling properties:
    repeat: bool = False
    when: Optional[datetime] = None
    interval: Optional[int] = None

    iterations: Optional[int] = None
    _iteration_counter: int = 0

    blackout_start_time: Optional[time] = None
    blackout_end_time: Optional[time] = None

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
        # If this is a repeating notification, it's already been sent once, and
        # we've exceeded our iterations, cancel right away:
        if (self.iterations and  # type: ignore
                self._iteration_counter == self.iterations and
                self._cancel_method):
            self._cancel_method()
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
                self._iteration_counter += 1

    def send(self) -> Callable:
        """Send the notification."""
        if self.when and self.interval:
            handle = self._app.run_every(
                self._send_cb, self.when, self.interval)
        elif self.when:
            handle = self._app.run_at(self._send_cb, self.when)
        else:
            self._send_cb({})

        def cancel():
            """Define a method to cancel the notification."""
            if self.when:
                self._app.cancel_timer(handle)

        self._cancel_method = cancel
        return cancel


def send_notification(
        app: Base,
        targets: List[str],
        message: str,
        title: str = None,
        when: datetime = None,
        interval: int = None,
        iterations: int = None) -> Callable:
    """Send/schedule a notification and return a method to cancel it."""
    notification = Notification(  # type: ignore
        app=app,
        targets=targets,
        message=message,
        title=title,
        when=when,
        interval=interval,
        iterations=iterations)
    return notification.send()
