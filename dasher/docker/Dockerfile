FROM mhart/alpine-node:10.8.0

RUN apk update \
    && apk add --update --virtual build-dependencies \
      build-base \
      git \
      libpcap-dev \
      python \
      python3 \
    && apk add --update \
      libpcap \
      sudo \
    && mkdir /usr/app \
    && cd /usr/app \
    && git clone https://github.com/maddox/dasher.git \
    && cd /usr/app/dasher \
    && npm config set registry http://registry.npmjs.org/ \
    && npm install \
    && apk del build-dependencies \
    && rm -rf /var/cache/apk/*

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

WORKDIR /usr/app/dasher
