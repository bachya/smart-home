#!/bin/sh

# Make a temp dir:
mkdir -p /tmp/geolite

# Download the latest DB:
wget -N -P /tmp/geolite https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.tar.gz
tar xzvf GeoLite2-Country.tar.gz -C /tmp/geolite --strip-components=1
mv /tmp/geolite/GeoLite2-Country.mmdb /usr/local/share/GeoIP/ \

# Delete the temp dir:
rm -rf /tmp/geolite

# Log:
echo "$(date +%Y-%m-%d\ %H:%m\ %p): Latest GeoLite2 database downloaded" >> /var/log/geolite-download.log
