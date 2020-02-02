"""Support for SimpliSafe alarm control panels."""
import logging
import re

from simplipy.errors import SimplipyError
from simplipy.system import SystemStates
from simplipy.websocket import (
    EVENT_ALARM_CANCELED,
    EVENT_ALARM_TRIGGERED,
    EVENT_ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_KEYPAD,
    EVENT_ARMED_AWAY_BY_REMOTE,
    EVENT_ARMED_HOME,
    EVENT_AWAY_EXIT_DELAY_BY_KEYPAD,
    EVENT_AWAY_EXIT_DELAY_BY_REMOTE,
    EVENT_DISARMED_BY_MASTER_PIN,
    EVENT_DISARMED_BY_REMOTE,
    EVENT_HOME_EXIT_DELAY,
)

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    FORMAT_TEXT,
    AlarmControlPanel,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    CONF_CODE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from . import SimpliSafeEntity
from .const import ATTR_LAST_EVENT_TYPE, DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_PIN_NAME = "pin_name"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a SimpliSafe alarm control panel based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            SimpliSafeAlarm(simplisafe, system, entry.data.get(CONF_CODE))
            for system in simplisafe.systems.values()
        ],
        True,
    )


class SimpliSafeAlarm(SimpliSafeEntity, AlarmControlPanel):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, simplisafe, system, code):
        """Initialize the SimpliSafe alarm."""
        super().__init__(system, "Alarm Control Panel")
        self._changed_by = None
        self._code = code
        self._last_event = None
        self._simplisafe = simplisafe
        self._state_manually_overriden = False

        if system.alarm_going_off:
            self._state = STATE_ALARM_TRIGGERED
        elif system.state == SystemStates.away:
            self._state = STATE_ALARM_ARMED_AWAY
        elif system.state in (
            SystemStates.away_count,
            SystemStates.exit_delay,
            SystemStates.home_count,
        ):
            self._state = STATE_ALARM_ARMING
        elif system.state == SystemStates.home:
            self._state = STATE_ALARM_ARMED_HOME
        elif system.state == SystemStates.off:
            self._state = STATE_ALARM_DISARMED
        else:
            self._state = None

    @property
    def changed_by(self):
        """Return info about who changed the alarm last."""
        return self._changed_by

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if not self._code:
            return None
        if isinstance(self._code, str) and re.search("^\\d+$", self._code):
            return FORMAT_NUMBER
        return FORMAT_TEXT

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, "disarming"):
            return

        try:
            await self._system.set_off()
        except SimplipyError as err:
            _LOGGER.error("Error while disarming system: %s", err)
            return

        self._state = STATE_ALARM_DISARMED

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, "arming home"):
            return

        try:
            await self._system.set_home()
        except SimplipyError as err:
            _LOGGER.error('Error while arming system ("home"): %s', err)
            return

        self._state = STATE_ALARM_ARMED_HOME

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, "arming away"):
            return

        try:
            await self._system.set_away()
        except SimplipyError as err:
            _LOGGER.error('Error while arming system ("away"): %s', err)
            return

        self._state = STATE_ALARM_ARMING

    async def async_update(self):
        """Update alarm status."""
        rest_data = self._simplisafe.last_rest_api_data[self._system.system_id]
        ws_data = self._simplisafe.last_websocket_data.get(self._system.system_id)

        # If the most recent REST API data (within the data object) doesn't match what
        # this entity last used, update:
        if self._last_used_rest_api_data != rest_data:
            self._last_used_rest_api_data = rest_data

            if self._system.state == SystemStates.error:
                self._online = False
                return
            self._online = True

            self._attrs.update(rest_data)

        # If the most recent websocket data (within the data object) doesn't match what
        # this entity last used, update:
        if self._last_used_websocket_data != ws_data:
            self._last_used_websocket_data = ws_data

            if ws_data.get(ATTR_PIN_NAME):
                self._changed_by = ws_data[ATTR_PIN_NAME]

            if ws_data[ATTR_LAST_EVENT_TYPE] in (
                EVENT_ALARM_CANCELED,
                EVENT_DISARMED_BY_MASTER_PIN,
                EVENT_DISARMED_BY_REMOTE,
            ):
                self._state = STATE_ALARM_DISARMED
            elif ws_data[ATTR_LAST_EVENT_TYPE] == EVENT_ALARM_TRIGGERED:
                self._state = STATE_ALARM_TRIGGERED
            elif ws_data[ATTR_LAST_EVENT_TYPE] in (
                EVENT_ARMED_AWAY,
                EVENT_ARMED_AWAY_BY_KEYPAD,
                EVENT_ARMED_AWAY_BY_REMOTE,
            ):
                self._state = STATE_ALARM_ARMED_AWAY
            elif ws_data[ATTR_LAST_EVENT_TYPE] == EVENT_ARMED_HOME:
                self._state = STATE_ALARM_ARMED_HOME
            elif ws_data[ATTR_LAST_EVENT_TYPE] in (
                EVENT_AWAY_EXIT_DELAY_BY_KEYPAD,
                EVENT_AWAY_EXIT_DELAY_BY_REMOTE,
                EVENT_HOME_EXIT_DELAY,
            ):
                self._state = STATE_ALARM_ARMING
            else:
                self._state = None

            self._attrs.update(ws_data)
