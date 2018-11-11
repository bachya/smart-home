ARG version

FROM homeassistant/home-assistant:$version

# Compile an up-to-date FFMpeg:
RUN apt-get update \
  && curl -sL https://deb.nodesource.com/setup_10.x | bash - \
  && apt-get install --no-install-recommends -y \
      nodejs \
  && npm install -g ps4-waker \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
