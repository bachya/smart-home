"""Define various constants."""
BLACKOUT_START = '22:00:00'
BLACKOUT_END = '08:00:00'

# Top level-related config keys:
CONF_ENTITY_IDS = 'entity_ids'
CONF_PROPERTIES = 'properties'

# Entity-related config keys:
CONF_DEVICE_TRACKERS = 'device_trackers'
CONF_ENTITY = 'entity'

# Name-related config keys:
CONF_FRIENDLY_NAME = 'friendly_name'

# State-related config keys:
CONF_STATE = 'state'

# Time-related config keys:
CONF_DELAY = 'delay'
CONF_DURATION = 'duration'
CONF_END_TIME = 'end_time'
CONF_START_TIME = 'start_time'
CONF_UPDATE_INTERVAL = 'update_interval'

# Constraint-related config keys:
CONF_CONSTRAIN_CLOUDY = 'constrain_cloudy'
CONF_CONSTRAIN_SUN = 'constrain_sun'

# Notification-related config keys:
CONF_NOTIFIERS = 'notifiers'
CONF_NOTIFICATION_INTERVAL = 'notification_interval'
CONF_NOTIFICATION_TARGET = 'notification_target'

# Misc. config keys:
CONF_PEOPLE = 'people'
CONF_TRIGGER_FIRST = 'trigger_on_first_only'

TOGGLE_STATES = ('closed', 'off', 'on', 'open')

THRESHOLD_CLOUDY = 70.0
