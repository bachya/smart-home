"""Define outdoor automations."""
from threading import Lock

from core import Base
from helpers.notification import send_notification

CONF_DISTANCE = "distance"
CONF_LIGHTNING_WINDOW = "notification_window_seconds"

EVENT_LIGHTNING_DETECTED = "LIGHTNING_DETECTED"


class LightningDetected(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify when lightning is detected."""

    def configure(self) -> None:
        """Configure."""
        self._active = False
        self._lock = Lock()

        self.listen_event(self._on_lightning_detected, EVENT_LIGHTNING_DETECTED)

    def _on_lightning_detected(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "LIGHTNING_DETECTED" events."""
        with self._lock:
            if self._active:
                return

            send_notification(
                self,
                "presence:home",
                f"Lightning detected {data[CONF_DISTANCE]} miles away.",
                title="Lightning Detected ⚡️",
            )

            self._active = True
            self.run_in(self._on_reset, self.args[CONF_LIGHTNING_WINDOW])

    def _on_reset(self, kwargs: dict) -> None:
        """Reset the notification window."""
        self._active = False
