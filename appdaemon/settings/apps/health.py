"""Define automations for health."""
from typing import Callable, Optional, Union

import voluptuous as vol

from const import CONF_ENTITY_IDS, CONF_PROPERTIES
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_AARON_ROUTER_TRACKER = "aaron_router_tracker"
CONF_AQI = "aqi"
CONF_AQI_THRESHOLD = "aqi_threshold"
CONF_HVAC_STATE = "hvac_state"


class AaronAccountability(Base):
    """Define features to keep me accountable on my phone."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_AARON_ROUTER_TRACKER): cv.entity_id},
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_disconnect,
            self.entity_ids[CONF_AARON_ROUTER_TRACKER],
            new="not_home",
            constrain_in_blackout=True,
            constrain_anyone="home",
        )

    @property
    def router_tracker_state(self) -> str:
        """Return the state of Aaron's Unifi tracker."""
        return self.get_state(self.entity_ids[CONF_AARON_ROUTER_TRACKER])

    def _on_disconnect(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send a notification when I disconnect during a blackout."""
        self._send_notification()

    def _send_notification(self) -> None:
        """Send notification to my love."""
        send_notification(
            self,
            "ios_brittany_bachs_iphone",
            "His phone shouldn't be off wifi during the night.",
            title="Check on Aaron",
        )


class NotifyBadAqi(Base):
    """Define a feature to notify us of bad air quality."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_AQI): cv.entity_id,
                    vol.Required(CONF_HVAC_STATE): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_AQI_THRESHOLD): int}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._bad_notification_sent = False
        self._good_notification_sent = False
        self._send_notification_func = None  # type: Optional[Callable]

        self.listen_state(
            self._on_aqi_change, self.entity_ids[CONF_HVAC_STATE], new="cooling"
        )

    @property
    def current_aqi(self) -> int:
        """Define a property to get the current AQI."""
        return int(self.get_state(self.entity_ids[CONF_AQI]))

    def _on_aqi_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send select notifications when cooling and poor AQI."""

        def _send_bad_notification():
            """Send a notification of bad AQI."""
            send_notification(
                self,
                "presence:home",
                "AQI is at {0}; consider closing the humidifier vent.".format(
                    self.current_aqi
                ),
                title="Poor AQI 😤",
            )

        def _send_good_notification():
            """Send a notification of good AQI."""
            send_notification(
                self,
                "presence:home",
                "AQI is at {0}; open the humidifer vent again.".format(
                    self.current_aqi
                ),
                title="Better AQI 😅",
            )

        if self.current_aqi > self.properties[CONF_AQI_THRESHOLD]:
            if self._bad_notification_sent:
                return

            self.log("Notifying anyone at home of bad AQI during cooling")
            self._bad_notification_sent = True
            self._good_notification_sent = False
            notification_func = _send_bad_notification
        else:
            if self._good_notification_sent:
                return

            self.log("Notifying anyone at home of AQI improvement during cooling")
            self._bad_notification_sent = False
            self._good_notification_sent = True
            notification_func = _send_good_notification

        # If the automation is enabled when a battery is low, send a notification;
        # if not, remember that we should send the notification when the automation
        # becomes enabled:
        if self.enabled:
            notification_func()
        else:
            self._send_notification_func = notification_func

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled (if appropriate)."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None
