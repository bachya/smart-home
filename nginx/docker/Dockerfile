FROM alpine:3.6

ARG geoip_version
ARG naxsi_version
ARG nginx_version

VOLUME /etc/nginx

# Update, install, and clean up packages all in one step:
RUN apk update \
    && apk add --update --virtual build-dependencies \
      build-base \
      ca-certificates \
      linux-headers \
      openssl-dev \
      pcre-dev \
      wget \
      zlib-dev \
    && apk add --update \
      fail2ban \
      openssl \
      pcre \
      rsyslog \
      supervisor \
      tzdata \
      zlib \
    && mkdir /tmp/src \
    && cd /tmp/src \
    && wget https://github.com/maxmind/geoip-api-c/releases/download/v${geoip_version}/GeoIP-${geoip_version}.tar.gz \
    && tar -zxvf GeoIP-${geoip_version}.tar.gz \
    && cd /tmp/src/GeoIP-${geoip_version} \
    && ./configure \
    && make \
    && make check \
    && make install \
    && cd /tmp/src \
    && wget -N http://geolite.maxmind.com/download/geoip/database/GeoLiteCountry/GeoIP.dat.gz \
    && gunzip GeoIP.dat.gz \
    && mkdir -p /usr/local/share/GeoIP/ \
    && mv GeoIP.dat /usr/local/share/GeoIP/ \
    && wget http://nginx.org/download/nginx-${nginx_version}.tar.gz \
    && wget https://github.com/nbs-system/naxsi/archive/${naxsi_version}.tar.gz \
    && tar -zxvf nginx-${nginx_version}.tar.gz \
    && tar -zxvf ${naxsi_version}.tar.gz \
    && cp /tmp/src/naxsi-${naxsi_version}/naxsi_config/naxsi_core.rules /etc/nginx/ \
    && cd /tmp/src/nginx-${nginx_version} \
    && ./configure \
      --add-module=../naxsi-${naxsi_version}/naxsi_src/ \
      --prefix=/etc/nginx \
      --sbin-path=/usr/local/sbin/nginx \
      --conf-path=/etc/nginx/nginx.conf \
      --pid-path=/run/nginx.pid \
      --lock-path=/run/nginx.lock \
      --http-log-path=/var/log/nginx/access.log \
      --error-log-path=/var/log/nginx/error.log \
      --with-pcre-jit \
      --with-http_ssl_module \
      --with-stream \
      --with-stream_ssl_module \
      --with-http_stub_status_module \
      --with-http_gzip_static_module \
      --with-http_v2_module \
      --with-http_auth_request_module \
      --with-http_geoip_module \
    && make \
    && make install \
    && apk del build-dependencies \
    && rm /usr/local/lib/libGeoIP.a \
    && rm -rf /tmp/src \
    && rm -rf /var/cache/apk/*

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# Copy configuration files:
RUN mkdir /var/run/fail2ban
COPY conf/supervisor/supervisor.conf /etc/supervisor.conf

# Create a www-data user and group:
RUN set -x ; \
    addgroup -g 82 -S www-data ; \
    adduser -u 82 -D -S -G www-data www-data && exit 0 ; exit 1

# Set up necessary NGINX directories, configs, etc.:
RUN mkdir -p /var/run/nginx \
    && mkdir -p /var/lib/nginx \
    && chown -R www-data:www-data /var/lib/nginx

WORKDIR /etc/nginx
