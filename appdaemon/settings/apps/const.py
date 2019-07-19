"""Define various constants."""
# Top level-related config keys:
CONF_ENTITY_IDS = "entity_ids"
CONF_PROPERTIES = "properties"

# Entity-related config keys:
CONF_DEVICE_TRACKERS = "device_trackers"
CONF_ENTITY_ID = "entity_id"
CONF_ICON = "icon"

# Name-related config keys:
CONF_FRIENDLY_NAME = "friendly_name"

# State-related config keys:
CONF_STATE = "state"

# Time-related config keys:
CONF_DELAY = "delay"
CONF_DURATION = "duration"
CONF_END_TIME = "end_time"
CONF_START_TIME = "start_time"
CONF_UPDATE_INTERVAL = "update_interval"

# Notification-related config keys:
CONF_MESSAGE = "message"
CONF_NOTIFICATION_INTERVAL = "notification_interval"
CONF_NOTIFICATION_TARGET = "notification_target"
CONF_NOTIFIERS = "notifiers"
CONF_TITLE = "title"

# Comparison-related config keys:
CONF_ABOVE = "above"
CONF_BELOW = "below"
CONF_EQUAL_TO = "equal_to"
COMPARITORS = (CONF_ABOVE, CONF_BELOW, CONF_EQUAL_TO)

# Collections of valid inputs:
OPERATOR_ALL = "all"
OPERATOR_ANY = "any"
OPERATORS = (OPERATOR_ALL, OPERATOR_ANY)
TOGGLE_STATES = ("closed", "off", "on", "open")

# Misc. config keys:
CONF_PEOPLE = "people"
CONF_TRIGGER_FIRST = "trigger_on_first_only"

# Events:
CONF_EVENT = "event"
CONF_EVENT_DATA = "event_data"
EVENT_ALARM_CHANGE = "ALARM_CHANGE"
EVENT_MODE_CHANGE = "MODE_CHANGE"
EVENT_PRESENCE_CHANGE = "PRESENCE_CHANGE"
EVENT_PROXIMITY_CHANGE = "PROXIMITY_CHANGE"
EVENT_VACUUM_START = "VACUUM_START"
