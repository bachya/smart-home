# Aaron's Smart Home ⭐

![The Home Screen](https://github.com/bachya/smart-home/wiki/img/default.png)

This repository contains (almost) everything needed to run my smart home. I
make the details freely available in the hope that other home automation
enthusiasts might find value.

I use an Intel NUC i5 with the following apps running as Docker containers:

* [ecowitt2mqtt](https://github.com/bachya/ecowitt2mqtt): sends local weather station data to Home Assistant
* [ESPHome](https://esphome.io/): custom firmware generator for ESP8266/ESP32 microcontrollers
* [Fail2Ban](https://www.fail2ban.org/wiki/index.php/Main_Page): an adaptive log monitor that can firewall bad IP addresses
* [Home Assistant](http://home-assistant.io): the primary home automation software
* [metrics2mqtt](https://github.com/jamiebegin/metrics2mqtt): sends host data (memory, CPU, disk usage, etc.) to an MQTT broker
* [OpenZWave](https://github.com/OpenZWave/qt-openzwave): sends data from Z-Wave devices to an MQTT broker
* [Portainer](https://www.portainer.io/): a GUI to manage my Docker containers when I'm sick of the CLI 😂
* [Traefik](https://traefik.io/traefik/): a fast, secure web server behind which the other services live
* [VerneMQ](https://vernemq.com/): an MQTT broker for fast, friendly service communication
* [zigbee2mqtt](https://vernemq.com/): sends data from Zigbee devices to an MQTT broker

# The Details

I do a _poor_ job keeping my wiki up to date, so if you want to know something, submit an issue!
