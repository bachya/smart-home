#!/bin/sh

# Start supervisor (and NGINX):
/usr/bin/supervisord -c /etc/supervisor.conf

# Start cron:
/usr/sbin/crond -f -l 8
