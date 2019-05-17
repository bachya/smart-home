"""Define various test automations."""
from core import Base
from notification_helper import send_notification


class TestNotification(Base):
    """Test notifications."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self.generic_notification_1, 'TEST_GENERIC_NOTIFICATION_1')
        self.listen_event(
            self.person_notification_1, 'TEST_PERSON_NOTIFICATION_1')
        self.listen_event(
            self.presence_notification_1, 'TEST_PRESENCE_NOTIFICATION_1')
        self.listen_event(
            self.slack_notification_1, 'TEST_SLACK_NOTIFICATION_1')
        self.listen_event(
            self.slack_notification_2, 'TEST_SLACK_NOTIFICATION_2')

    def generic_notification_1(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a generic notification."""
        send_notification(self, 'mobile_app_iphone', 'This is a test')

    def person_notification_1(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a person notification."""
        send_notification(self, 'person:Aaron', 'This is a test')

    def presence_notification_1(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a presence notification to all "away" people."""
        send_notification(self, 'presence:away', 'This is a test')

    def slack_notification_1(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a Slack notification to a person in the default channel."""
        send_notification(self, 'slack:@aaron', 'This is a test')

    def slack_notification_2(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Test a Slack notification to a person in a specific channel."""
        send_notification(self, 'slack:no-rush/@aaron', 'This is a test')
