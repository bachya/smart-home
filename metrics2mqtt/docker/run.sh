#!/bin/sh
if [ -z "${MQTT_BROKER}" ]; then
    echo 'Missing required environment variable: $MQTT_BROKER'
    exit 1
fi

if [ -z "${MQTT_USERNAME}" ]; then
    echo 'Missing required environment variable: $MQTT_USERNAME'
    exit 1
fi

if [ -z "${MQTT_PASSWORD}" ]; then
    echo 'Missing required environment variable: $MQTT_PASSWORD'
    exit 1
fi

M2M_OPTIONS_STRING="--broker ${MQTT_BROKER} --username ${MQTT_USERNAME} --password ${MQTT_PASSWORD}"

if [ ! -z "${COMMAND_OPTIONS_STRING}" ]; then
    M2M_OPTIONS_STRING="${M2M_OPTIONS_STRING} ${COMMAND_OPTIONS_STRING}"
fi

# Store the options string as an environment variable that supervisor can use:
export M2M_OPTIONS_STRING

/usr/bin/supervisord -c /etc/supervisor.conf
