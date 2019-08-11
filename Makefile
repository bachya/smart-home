test:
	docker run --rm -v `pwd`/nginx/settings/nginx:/etc/nginx:ro yandex/gixy /etc/nginx/nginx.conf
	docker run -it --rm -v `pwd`/home-assistant/settings:/config:ro homeassistant/amd64-homeassistant hass -c /config --script check_config
	for file in $(find esphome -type f -name "*.yaml" -not -name "secrets.yaml"); do docker run --rm -v "${PWD}/esphome":/config -it esphome/esphome master_bedroom_salt_lamp.yaml config; done
