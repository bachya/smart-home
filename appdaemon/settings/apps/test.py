"""Define various test automations."""
from datetime import datetime, timedelta

from core import Base
from helpers.notification import send_notification


class TestNotification(Base):
    """Test notifications."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(self.generic_notification_1, "TEST_GENERIC_NOTIFICATION_1")
        self.listen_event(self.person_notification_1, "TEST_PERSON_NOTIFICATION_1")
        self.listen_event(self.person_notification_2, "TEST_PERSON_NOTIFICATION_2")
        self.listen_event(self.person_notification_3, "TEST_PERSON_NOTIFICATION_3")
        self.listen_event(self.presence_notification_1, "TEST_PRESENCE_NOTIFICATION_1")
        self.listen_event(self.slack_notification_1, "TEST_SLACK_NOTIFICATION_1")
        self.listen_event(self.slack_notification_2, "TEST_SLACK_NOTIFICATION_2")
        self.listen_event(self.slack_notification_3, "TEST_SLACK_NOTIFICATION_3")

    def generic_notification_1(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a single, immediate notifier notification."""
        send_notification(self, "mobile_app_iphone", "This is a test")

    def person_notification_1(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a single, immediate person notification."""
        send_notification(self, "person:Aaron", "This is a test")

    def person_notification_2(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a single, scheduled person notification."""
        send_notification(
            self,
            "person:Aaron",
            "This is a test",
            title="Yeehaw",
            when=datetime.now() + timedelta(seconds=30),
        )

    def person_notification_3(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a single, scheduled person notification that gets canceled."""
        cancel_notification = send_notification(
            self,
            "person:Aaron",
            "This is a test",
            title="Yeehaw",
            when=datetime.now() + timedelta(seconds=30),
        )
        cancel_notification()

    def presence_notification_1(
        self, event_name: str, data: dict, kwargs: dict
    ) -> None:
        """Test a single, immediate presence notification."""
        send_notification(self, "presence:away", "This is a test")

    def slack_notification_1(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a single, immediate Slack notification."""
        send_notification(self, "slack:@aaron", "This is a test")

    def slack_notification_2(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a repeating Slack notification."""
        send_notification(
            self, "slack:@aaron", "This is a test", when=self.datetime(), interval=15
        )

    def slack_notification_3(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a repeating Slack notification that stops after 3 sends."""
        send_notification(
            self,
            "slack",
            "This is a test",
            when=self.datetime(),
            interval=15,
            iterations=3,
        )
