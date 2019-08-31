#!/bin/sh

# Load our crontab:
/usr/bin/crontab /opt/crontab.txt

# Start crond:
usr/sbin/crond -f -l 8
