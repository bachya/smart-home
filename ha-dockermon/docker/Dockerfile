FROM alpine:3.6

ARG version

ENV HA_DOCKERMON_VERSION=$version

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN apk update \
    && apk add --update \
      nodejs \
      nodejs-npm \
      supervisor \
      tzdata \
    && apk add --update --virtual build-dependencies \
      git \
    && git clone https://github.com/philhawthorne/ha-dockermon.git /usr/src/app \
    && git checkout tags/v${version} \
    && npm install \
    && apk del build-dependencies \
    && rm -rf /var/cache/apk/*

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# Copy configuration files:
COPY start.sh /usr/src/app/start.sh
COPY conf/supervisor/supervisor.conf /etc/supervisor.conf
