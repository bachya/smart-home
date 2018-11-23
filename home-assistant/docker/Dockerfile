ARG hass_version
ARG ps4waker_version

FROM homeassistant/home-assistant:$hass_version

# Compile an up-to-date FFMpeg:
RUN apt-get update \
  && curl -sL https://deb.nodesource.com/setup_10.x | bash - \
  && apt-get install --no-install-recommends -y \
      nodejs \
  && npm install -g ps4-waker@${ps4waker_version} \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
