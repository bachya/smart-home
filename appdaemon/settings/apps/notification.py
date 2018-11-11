"""Define a notification mechanism for all AppDaemon apps."""
# pylint: disable=unused-import

from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, List, Union  # noqa
from uuid import UUID

from automation import Base  # type: ignore
from const import BLACKOUT_END, BLACKOUT_START, PEOPLE  # type: ignore
from util.dt import time_is_between  # type: ignore


class NotificationTypes(Enum):
    """Define an enum for notification types."""

    single = 1
    repeating = 2


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class Notification:
    """Define a notification object."""

    def __init__(self, kind, message, *, title=None, **kwargs):
        """Initialize."""
        self.blackout_end_time = kwargs.get('blackout_end_time')
        self.blackout_start_time = kwargs.get('blackout_start_time')
        self.cancel = None
        self.interval = kwargs.get('interval')
        self.kind = kind
        self.message = message
        self.target = kwargs.get('target')
        self.title = title
        self.when = kwargs.get('when')

        self.data = kwargs.get('data')
        if self.data is None:
            self.data = {}
        self.data.setdefault('push', {})
        self.data['push'].setdefault(
            'thread-id', '{0}_{1}'.format(title, message))

    def __eq__(self, other):
        """Define method to compare notification objects."""
        return self.__dict__ == other.__dict__


class NotificationManager(Base):
    """Define an app to act as a system-wide notifier."""

    # pylint: disable=attribute-defined-outside-init
    def initialize(self):
        """Initialize."""
        super().initialize()

        self.registry = []

        self.listen_event(self._notifier_test_cb, 'NOTIFIER_TEST')

    def _adjust_for_blackout(self, notification: Notification) -> Notification:
        """Reschedule a notification's schedule for outside of blackout."""
        if self._in_blackout(notification):
            if notification.when:
                target_date = notification.when.date()
                active_time = notification.when.time()
            else:
                target_date = self.date()
                active_time = self.time()

            if active_time > self.parse_time(notification.blackout_end_time):
                target_date = target_date + timedelta(days=1)

            notification.when = datetime.combine(
                target_date, self.parse_time(notification.blackout_end_time))
        else:
            notification.when = self.datetime() + timedelta(seconds=1)

        return notification

    def _get_targets(self, target: Union[str, list]) -> list:
        """Get a list of targets based on input string."""
        if isinstance(target, str):
            _targets = [target]
        else:
            _targets = target

        targets = []  # type: List[str]
        for item in _targets:
            split = item.split(' ')  # type: ignore

            # 1. target='not Person'
            if split[0] == 'not' and split[1] in PEOPLE:
                targets += [
                    notifier for name, attrs in PEOPLE.items()
                    if name != split[1] for notifier in attrs['notifiers']
                ]

            # 2. target='Person'
            elif split[0] in PEOPLE:
                targets += PEOPLE[item]['notifiers']

            else:
                try:
                    # 3. target='home'
                    targets += [
                        notifier for name in getattr(
                            self.presence_manager, 'whos_{0}'.format(item))()
                        for notifier in PEOPLE[name]['notifiers']
                    ]
                except AttributeError:
                    # 4. target='everyone'
                    if item == 'everyone':
                        targets += [
                            notifier for attrs in PEOPLE.values()
                            for notifier in attrs['notifiers']
                        ]

                    # 5. target='person_iphone'
                    else:
                        targets.append(item)

        return targets

    def _in_blackout(self, notification: Notification) -> bool:
        """Determine whether a notification is set to send in blackout."""
        if (not notification.blackout_start_time
                or not notification.blackout_end_time):
            return False

        if notification.when:
            return time_is_between(
                self, notification.when, notification.blackout_start_time,
                notification.blackout_end_time)

        return self.now_is_between(
            notification.blackout_start_time, notification.blackout_end_time)

    def _notifier_test_cb(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Run a test."""
        try:
            kind = data['kind']
            message = data['message']
        except KeyError:
            self.error('Missing message and/or kind in notifier test')
            return

        _data = data.get('data', None)
        blackout_end_time = data.get('blackout_end_time', BLACKOUT_END)
        blackout_start_time = data.get('blackout_start_time', BLACKOUT_START)
        interval = data.get('interval', None)
        target = data.get('target', None)
        title = data.get('title', None)
        when = data.get('when', None)

        if kind == NotificationTypes.single.name:
            self.send(
                message,
                title=title,
                when=when,
                target=target,
                data=_data,
                blackout_start_time=blackout_start_time,
                blackout_end_time=blackout_end_time)
        elif kind == NotificationTypes.repeating.name:
            self.repeat(
                message,
                interval,
                title=title,
                when=when,
                target=target,
                data=_data,
                blackout_start_time=blackout_start_time,
                blackout_end_time=blackout_end_time)

    def _send_cb(self, kwargs: dict) -> None:
        """Send a single (immediate or scheduled) notification."""
        notification = kwargs['notification']

        # If an instance of a repeating notification occurs in the blackout,
        # we should cancel the entire series and resume when the blackout
        # lifts. Setting `notification.when` to `None` forces a check for
        # whether we're currently in the blackout, rather than a check for
        # whether the notification's original `when` is in the blackout.
        if notification.kind == NotificationTypes.repeating:
            notification.when = None
            if self._in_blackout(notification):
                notification.cancel()
                self.dispatch(notification)
                return

        for target in self._get_targets(notification.target):
            self.call_service(
                'notify/{0}'.format(target),
                message=notification.message,
                title=notification.title,
                data=notification.data)

        if notification.kind == NotificationTypes.single:
            self.registry.remove(notification)

    def create_omnifocus_task(self, title: str) -> None:
        """Create a task in Aaron's omnifocus."""
        self.notify(
            'created on {0}'.format(str(self.datetime())),
            title=title,
            name='omnifocus')

    def create_persistent_notification(self, title: str, message: str) -> None:
        """Create a notification in the HASS UI."""
        self.call_service(
            'persistent_notification/create', title=title, message=message)

    def dispatch(self, notification: Notification) -> Callable:
        """Store and dispatch a notification, returning a cancel method."""
        notification = self._adjust_for_blackout(notification)

        if not notification.target:
            notification.target = 'everyone'

        if notification.kind == NotificationTypes.single:
            handle = self.run_at(
                self._send_cb, notification.when, notification=notification)
        else:
            handle = self.run_every(
                self._send_cb,
                notification.when,
                notification.interval,
                notification=notification)

        def cancel(delete: bool = True) -> None:
            """Define a method to cancel and return the notification."""
            self.cancel_timer(handle)
            if delete:
                self.registry.remove(notification)

        notification.cancel = cancel
        self.registry.append(notification)

        return cancel

    @staticmethod
    def get_target_from_push_id(push_id: UUID) -> Union[str, None]:
        """Return a person from a provided permanent device ID."""
        try:
            [target] = [
                k for k, v in PEOPLE.items() if v['push_device_id'] == push_id
            ]
        except ValueError:
            target = None

        return target

    def repeat(  # pylint: disable=too-many-arguments
            self,
            message: str,
            interval: int,
            *,
            title: str = None,
            when: Union[datetime, None] = None,
            target: Union[str, list, None] = None,
            data: Union[dict, None] = None,
            blackout_start_time: str = BLACKOUT_START,
            blackout_end_time: str = BLACKOUT_END) -> Callable:
        """Send a repeating notification to one or more targets."""
        return self.dispatch(
            Notification(
                NotificationTypes.repeating,
                message,
                title=title,
                blackout_end_time=blackout_end_time,
                blackout_start_time=blackout_start_time,
                data=data,
                interval=interval,
                target=target,
                when=when))

    def send(  # pylint: disable=too-many-arguments
            self,
            message: str,
            *,
            title: str = None,
            when: Union[datetime, None] = None,
            target: Union[str, list, None] = None,
            data: Union[dict, None] = None,
            blackout_start_time: str = BLACKOUT_START,
            blackout_end_time: str = BLACKOUT_END) -> Callable:
        """Send a notification to one or more targets."""
        return self.dispatch(
            Notification(
                NotificationTypes.single,
                message,
                title=title,
                blackout_end_time=blackout_end_time,
                blackout_start_time=blackout_start_time,
                data=data,
                target=target,
                when=when))
