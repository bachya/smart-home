#!/bin/sh

# Store the AppDaemon version locally:
echo $APPDAEMON_VERSION > /shared/.AD_VERSION

# Give HASS time to get its feet under it:
sleep 15

# Start app services:
/usr/bin/supervisord -c /etc/supervisor.conf
