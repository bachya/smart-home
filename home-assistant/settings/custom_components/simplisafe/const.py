"""Define constants for the SimpliSafe component."""
from datetime import timedelta

DOMAIN = "simplisafe"

DATA_CLIENT = "client"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

ATTR_ALARM_DURATION = "alarm_duration"
ATTR_ALARM_VOLUME = "alarm_volume"
ATTR_BATTERY_BACKUP_POWER_LEVEL = "battery_backup_power_level"
ATTR_CHIME_VOLUME = "chime_volume"
ATTR_ENTRY_DELAY_AWAY = "entry_delay_away"
ATTR_ENTRY_DELAY_HOME = "entry_delay_home"
ATTR_EXIT_DELAY_AWAY = "exit_delay_away"
ATTR_EXIT_DELAY_HOME = "exit_delay_home"
ATTR_GSM_STRENGTH = "gsm_strength"
ATTR_LAST_EVENT_INFO = "last_event_info"
ATTR_LAST_EVENT_SENSOR_NAME = "last_event_sensor_name"
ATTR_LAST_EVENT_SENSOR_TYPE = "last_event_sensor_type"
ATTR_LAST_EVENT_TIMESTAMP = "last_event_timestamp"
ATTR_LAST_EVENT_TYPE = "last_event_type"
ATTR_LIGHT = "light"
ATTR_RF_JAMMING = "rf_jamming"
ATTR_VOICE_PROMPT_VOLUME = "voice_prompt_volume"
ATTR_WALL_POWER_LEVEL = "wall_power_level"
ATTR_WIFI_STRENGTH = "wifi_strength"
