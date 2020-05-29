#!/bin/sh

# Make a temp dir:
mkdir -p /tmp/src

# Download the latest DB:
wget -O /tmp/src/GeoLite2-Country.tar.gz "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key=fCICsoZwXeb3gTO9&suffix=tar.gz"
tar xzvf /tmp/src/GeoLite2-Country.tar.gz -C /tmp/src --strip-components=1
mv /tmp/src/GeoLite2-Country.mmdb /usr/local/share/GeoIP

# Delete the temp dir:
rm -rf /tmp/src

# Log:
echo "$(date +%Y-%m-%d\ %H:%m\ %p): Latest GeoLite2 database downloaded" >> /var/log/geolite-download.log
