FROM alpine:3.6

RUN apk add --update \
      mosquitto \
      mosquitto-clients \
      supervisor \
      tzdata \
    && rm -rf /var/cache/apk/*

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# Copy configuration files:
COPY conf/supervisor/supervisor.conf /etc/supervisor.conf

CMD ["supervisord", "-c", "/etc/supervisor.conf"]
