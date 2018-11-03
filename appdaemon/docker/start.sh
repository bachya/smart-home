#!/bin/sh

# Store the AppDaemon version locally:
echo $APPDAEMON_VERSION > /shared/.AD_VERSION

# Start app services:
/usr/bin/supervisord -c /etc/supervisor.conf
