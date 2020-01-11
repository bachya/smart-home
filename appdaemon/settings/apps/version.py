"""Define automations for tracking software versions."""
from typing import Callable, Optional, Union

import requests
import voluptuous as vol

from packaging import version

from core import APP_SCHEMA, Base
from const import (
    CONF_ENTITY_IDS,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    CONF_INTERVAL,
    CONF_PROPERTIES,
)
from helpers import config_validation as cv
from notification import send_notification

CONF_APP_NAME = "app_name"
CONF_AVAILABLE = "available"
CONF_CREATED_ENTITY_ID = "created_entity_id"
CONF_ENDPOINT_ID = "endpoint_id"
CONF_IMAGE_NAME = "image_name"
CONF_INSTALLED = "installed"
CONF_VERSION_SENSORS = "version_sensors"

ENTITY_IDS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AVAILABLE): cv.entity_id,
        vol.Required(CONF_INSTALLED): cv.entity_id,
    },
    extra=vol.ALLOW_EXTRA,
)

PROPERTIES_SCHEMA = vol.Schema(
    {vol.Required(CONF_APP_NAME): str}, extra=vol.ALLOW_EXTRA
)

VERSION_APP_SCHEMA = APP_SCHEMA.extend(
    {
        vol.Optional(CONF_ENTITY_IDS): ENTITY_IDS_SCHEMA,
        vol.Optional(CONF_PROPERTIES): PROPERTIES_SCHEMA,
    }
)

DYNAMIC_APP_SCHEMA = VERSION_APP_SCHEMA.extend(
    {
        vol.Required(CONF_PROPERTIES): PROPERTIES_SCHEMA.extend(
            {
                vol.Required(CONF_CREATED_ENTITY_ID): cv.entity_id,
                vol.Required(CONF_FRIENDLY_NAME): str,
                vol.Required(CONF_ICON): str,
                vol.Required(CONF_INTERVAL): int,
            }
        )
    }
)


class NewVersionNotification(Base):  # pylint: disable=too-few-public-methods
    """Detect new versions of apps."""

    APP_SCHEMA = VERSION_APP_SCHEMA

    def configure(self) -> None:
        """Configure."""
        self._send_notification_func = None  # type: Optional[Callable]

        self.listen_state(self._on_version_change, self.entity_ids[CONF_AVAILABLE])

    def _on_version_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Notify me when there's a new app version."""
        new_version = version.parse(self.get_state(self.entity_ids[CONF_AVAILABLE]))
        installed_version = version.parse(
            self.get_state(self.entity_ids[CONF_INSTALLED])
        )

        def _send_notification() -> None:
            """Send a notification about the new version."""
            send_notification(
                self,
                "slack:@aaron",
                f"New {self.properties[CONF_APP_NAME]} Version: {new_version}",
                title="New Software 💿",
            )

        if new_version > installed_version:
            self.log("New %s version detected: %s", self.properties[CONF_APP_NAME], new)
            if self.enabled:
                _send_notification()
            else:
                self._send_notification_func = _send_notification

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None


class DynamicSensor(NewVersionNotification):
    """Generate a dynamic version sensor."""

    APP_SCHEMA = DYNAMIC_APP_SCHEMA

    def configure(self) -> None:
        """Configure."""
        super().configure()
        self.run_every(self._on_update, self.datetime(), self.properties[CONF_INTERVAL])

    @property
    def sensor_value(self) -> Optional[str]:
        """Raise if not implemented."""
        raise NotImplementedError()

    def _on_update(self, kwargs: dict) -> None:
        """Update sensor value."""
        self.set_state(
            self.properties[CONF_CREATED_ENTITY_ID],
            state=str(self.sensor_value),
            attributes={
                "friendly_name": self.properties[CONF_FRIENDLY_NAME],
                "icon": self.properties[CONF_ICON],
            },
        )


class NewMultiSensorVersionNotification(DynamicSensor):
    """Detect version changes by examining multiple version sensors."""

    APP_SCHEMA = DYNAMIC_APP_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_IDS): ENTITY_IDS_SCHEMA.extend(
                {vol.Required(CONF_VERSION_SENSORS): vol.All(cv.ensure_list)}
            )
        }
    )

    @property
    def sensor_value(self) -> Optional[str]:
        """Determine the lowest value from the sensor list."""
        lowest_version = None
        for entity_id in self.entity_ids[CONF_VERSION_SENSORS]:
            ver = version.parse(self.get_state(entity_id))
            try:
                if ver < lowest_version:
                    lowest_version = ver
            except TypeError:
                lowest_version = ver

        return str(lowest_version)


class NewPortainerVersionNotification(DynamicSensor):
    """Detect new versions of Portainer-defined images."""

    APP_SCHEMA = DYNAMIC_APP_SCHEMA.extend(
        {
            vol.Required(CONF_PROPERTIES): PROPERTIES_SCHEMA.extend(
                {
                    vol.Required(CONF_ENDPOINT_ID): int,
                    vol.Required(CONF_IMAGE_NAME): str,
                }
            )
        }
    )

    API_URL = "http://portainer:9000/api"

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_AVAILABLE): cv.entity_id,
                    vol.Required(CONF_INSTALLED): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_APP_NAME): str}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    @property
    def sensor_value(self) -> Optional[str]:
        """Get the version from Portainer."""
        auth_resp = requests.post(
            f"{self.API_URL}/auth",
            json={
                "Username": self.config["portainer_username"],
                "Password": self.config["portainer_password"],
            },
        ).json()
        token = auth_resp["jwt"]

        images_resp = requests.get(
            (
                f"{self.API_URL}/endpoints/{self.properties[CONF_ENDPOINT_ID]}"
                "/docker/images/json"
            ),
            headers={"Authorization": f"Bearer {token}"},
        ).json()

        try:
            tagged_image = next(
                (
                    i
                    for image in images_resp
                    for i in image["RepoTags"]
                    if self.properties[CONF_IMAGE_NAME] in i
                )
            )
        except StopIteration:
            self.error("No match for image: %s", self.properties[CONF_IMAGE_NAME])
            return None

        return tagged_image.split(":")[1].replace("v", "").split("-")[0]
