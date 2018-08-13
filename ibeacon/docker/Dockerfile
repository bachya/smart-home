FROM debian:stretch-20180716

RUN sed -i "s/httpredir.debian.org/debian.ethz.ch/" /etc/apt/sources.list \
    && apt-get clean \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      bluez \
      bluetooth \
      sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/ /var/tmp/* /tmp/*

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# Create a space for app scripts to live:
RUN mkdir -p /usr/src/app/build
WORKDIR /usr/src/app
COPY run.sh .

CMD [ "/usr/src/app/run.sh" ]
