FROM alpine:3.10.1

ARG version

RUN apk update \
    && apk add --update \
      bash \
      build-base \
      ca-certificates \
      coreutils \
      linux-headers \
      python3 \
      python3-dev \
      supervisor \
      tzdata \
    && pip3 install --upgrade \
      pip \
      glances==${version} \
      bottle \
      docker \
      hddtemp \
      pySMART.smartx \
    && rm -rf /var/cache/apk/*

# Get timezone stuff set up correctly:
ENV TZ=America/Denver
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "$TZ" > /etc/timezone

# Copy configuration files:
COPY conf/supervisor/supervisor.conf /etc/supervisor.conf

# Run Supervisor:
WORKDIR /root
