#!/bin/sh

# Store the AppDaemon version locally:
echo $HA_DOCKERMON_VERSION > /shared/.HADM_VERSION

# Start app services:
/usr/bin/supervisord -c /etc/supervisor.conf
