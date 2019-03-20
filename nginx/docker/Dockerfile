FROM alpine:3.9

ARG maxminddb_version
ARG nginx_version
ARG ngx_http_geoip2_module_version

VOLUME /etc/nginx

# Update, install, and clean up packages all in one step:
RUN apk update \
    && apk add --no-cache --virtual build-dependencies \
      apk-cron \
      build-base \
      ca-certificates \
      linux-headers \
      openssl-dev \
      pcre-dev \
      wget \
      zlib-dev \
    && apk add --update \
      fail2ban \
      gzip \
      mosquitto-clients \
      openssl \
      pcre \
      perl \
      rsyslog \
      supervisor \
      tzdata \
      zlib \
    && mkdir /tmp/src \
    && wget -N -P /tmp/src https://github.com/maxmind/libmaxminddb/releases/download/${maxminddb_version}/libmaxminddb-${maxminddb_version}.tar.gz \
    && tar xzvf /tmp/src/libmaxminddb-${maxminddb_version}.tar.gz -C /tmp/src \
    && cd /tmp/src/libmaxminddb-${maxminddb_version} \
    && ./configure \
    && make \
    && make check \
    && make install \
    && ldconfig /usr/local/lib \
    && mkdir -p /usr/local/share/GeoIP/ \
    && wget -N -P /tmp/src https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.tar.gz \
    && tar xzvf /tmp/src/GeoLite2-Country.tar.gz -C /tmp/src --strip-components=1 \
    && mv /tmp/src/GeoLite2-Country.mmdb /usr/local/share/GeoIP \
    && wget -N -P /tmp/src https://github.com/leev/ngx_http_geoip2_module/archive/${ngx_http_geoip2_module_version}.tar.gz \
    && tar xzvf /tmp/src/${ngx_http_geoip2_module_version}.tar.gz -C /tmp/src \
    && wget -N -P /tmp/src http://nginx.org/download/nginx-${nginx_version}.tar.gz \
    && tar -zxvf /tmp/src/nginx-${nginx_version}.tar.gz -C /tmp/src \
    && cd /tmp/src/nginx-${nginx_version} \
    && ./configure \
      --add-module=/tmp/src/ngx_http_geoip2_module-${ngx_http_geoip2_module_version} \
      --conf-path=/etc/nginx/nginx.conf \
      --error-log-path=/var/log/nginx/error.log \
      --http-log-path=/var/log/nginx/access.log \
      --lock-path=/run/nginx.lock \
      --pid-path=/run/nginx.pid \
      --prefix=/etc/nginx \
      --sbin-path=/usr/local/sbin/nginx \
      --with-http_auth_request_module \
      --with-http_gzip_static_module \
      --with-http_ssl_module \
      --with-http_stub_status_module \
      --with-http_v2_module \
      --with-pcre-jit \
      --with-stream \
      --with-stream_ssl_module \
    && make \
    && make install \
    && apk del build-dependencies \
    && rm -rf /tmp/src \
    && rm -rf /var/cache/apk/*

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# Create a www-data user and group:
RUN set -x ; \
    addgroup -g 82 -S www-data ; \
    adduser -u 82 -D -S -G www-data www-data && exit 0 ; exit 1

# Set up configuration structures:
COPY geolite-download.sh /geolite-download.sh
COPY bin/fail2ban-mqtt-notifier /usr/local/bin/fail2ban-mqtt-notifier
COPY conf/supervisor/supervisor.conf /etc/supervisor.conf
COPY conf/crontab.txt /crontab.txt
RUN mkdir -p /var/run/nginx \
    && mkdir -p /var/lib/nginx \
    && chown -R www-data:www-data /var/lib/nginx \
    && chmod 755 /geolite-download.sh \
    && chmod 755 /usr/local/bin/fail2ban-mqtt-notifier \
    && /usr/bin/crontab /crontab.txt
