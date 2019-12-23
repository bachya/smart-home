"""Define automations to call services in specific scenarios."""
import voluptuous as vol

from const import CONF_EVENT, CONF_EVENT_DATA, CONF_PROPERTIES
from core import APP_SCHEMA, Base

CONF_RUN_ON_DAYS = "run_on_days"
CONF_SCHEDULE_TIME = "schedule_time"
CONF_SERVICE = "service"
CONF_SERVICE_DATA = "service_data"

SERVICE_CALL_SCHEMA = APP_SCHEMA.extend(
    {vol.Required(CONF_SERVICE): str, vol.Required(CONF_SERVICE_DATA): dict}
)


class ServiceBase(Base):  # pylint: disable=too-few-public-methods
    """Define a base automation for calling services."""

    def service_callback(self, kwargs: dict) -> None:
        """Call the service at the configured time."""
        self.call_service(self.args[CONF_SERVICE], **self.args[CONF_SERVICE_DATA])


class ServiceAtEvent(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service upon seeing an specific event/payload."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_EVENT): str, vol.Optional(CONF_EVENT_DATA): dict},
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self.service_callback,
            self.properties[CONF_EVENT],
            **self.properties.get(CONF_EVENT_DATA, {}),
            constrain_enabled=True,
        )


class ServiceAtTime(Base):  # pylint: disable=too-few-public-methods
    """Define an automation to call a service at a specific time."""

    APP_SCHEMA = SERVICE_CALL_SCHEMA.extend(
        {
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_SCHEDULE_TIME): str}, extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.run_daily(
            self.service_callback,
            self.parse_time(self.properties[CONF_SCHEDULE_TIME]),
            constrain_enabled=True,
            auto_constraints=True,
        )
