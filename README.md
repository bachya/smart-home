# Aaron's Smart Home ⭐

![The Home Screen](https://github.com/bachya/smart-home/wiki/img/home.png)

This repository contains (almost) everything needed to run my smart home. I
make the details freely available in the hope that other home automation
enthusiasts might find value.

I use an Intel NUC i5 with the following apps running as Docker containers:

* [Home Assistant](http://home-assistant.io): the primary home automation software
* [AppDaemon](https://appdaemon.readthedocs.io/en/latest/): Home Assistant-friendly automation in pure Python
* [Dasher](https://github.com/maddox/dasher): a service allowing Amazon Dash buttons to interact with the system
* [Glances](https://nicolargo.github.io/glances/): system monitoring and stats
* [Grafana](https://grafana.com/): data visualization and analytics
* [ha-dockermon](https://github.com/philhawthorne/ha-dockermon): RESTful services to interact with Docker containers
* iBeacon: a container that allows my hub to act as an iBeacon for presence detection
* [Mosquitto](https://mosquitto.org/): an MQTT broker for fast, friendly service communication
* [NGINX](https://www.nginx.com/): a fast, secure web server behind which the other services live

# The Details

I keep all the nitty gritty details in the
[wiki](https://github.com/bachya/smart-home/wiki).
