FROM alpine:3.12

# Update, install, and clean up packages all in one step:
RUN apk update \
    && apk add --no-cache \
      bash \
      gzip \
      mosquitto-clients

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# Set up configuration structures:
COPY bin/fail2ban-mqtt-notifier /usr/local/bin/fail2ban-mqtt-notifier
COPY conf/crontab.txt /opt/crontab.txt
COPY conf/entry.sh /entry.sh
