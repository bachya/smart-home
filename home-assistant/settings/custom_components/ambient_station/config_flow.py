"""Config flow to configure the Ambient PWS component."""
from aioambient import Client
from aioambient.errors import AmbientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import aiohttp_client

from .const import CONF_APP_KEY, DOMAIN  # pylint: disable=unused-import


class AmbientStationFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Ambient PWS config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self.data_schema = vol.Schema(
            {vol.Required(CONF_API_KEY): str, vol.Required(CONF_APP_KEY): str}
        )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.data_schema,
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        await self.async_set_unique_id(user_input[CONF_APP_KEY])
        self._abort_if_unique_id_configured()

        session = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(
            user_input[CONF_API_KEY], user_input[CONF_APP_KEY], session=session
        )

        try:
            devices = await client.api.get_devices()
        except AmbientError:
            return await self._show_form({"base": "invalid_key"})

        if not devices:
            return await self._show_form({"base": "no_devices"})

        # The Application Key (which identifies each config entry) is too long
        # to show nicely in the UI, so we take the first 12 characters (similar
        # to how GitHub does it):
        return self.async_create_entry(
            title=user_input[CONF_APP_KEY][:12], data=user_input
        )
