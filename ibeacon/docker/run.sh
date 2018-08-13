#!/bin/bash
source /config/ibeacon.config

# Make sure the Bluetooth stack is up:
sudo hciconfig hci0 up
sudo hciconfig hci0 noscan

# Set appropriate advertising parameters:
sudo hcitool -i hci0 cmd \
  $advertising_begin_command \
  $advertising_min_interval \
  $advertising_max_interval \
  $advertising_mode \

# Enable advertising:
sudo hcitool -i hci0 cmd \
  $ibeacon_begin_command \
  $ibeacon_length \
  $ibeacon_company \
  $ibeacon_uuid \
  $ibeacon_major \
  $ibeacon_minor \
  $ibeacon_txpower \
  $ibeacon_end_command

# Activate advertising:
sudo hcitool -i hci0 cmd \
  $activate_begin_command \
  $activate_on
