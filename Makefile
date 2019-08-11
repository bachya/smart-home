THIS_FILE := $(lastword $(MAKEFILE_LIST))
ci:
	@$(MAKE) -f $(THIS_FILE) test
	@$(MAKE) -f $(THIS_FILE) lint

clean:
	pipenv --rm

init:
	pip3 install --upgrade pip pipenv
	pipenv lock
	pipenv install --three --dev

lint:
	pipenv run flake8 appdaemon/settings/apps
	pipenv run mypy --ignore-missing-imports appdaemon/settings/apps
	pipenv run pylint --rcfile appdaemon/settings/pylintrc appdaemon/settings/apps
	pipenv run yamllint appdaemon/settings/
	pipenv run yamllint esphome/
	pipenv run yamllint home-assistant/settings/
	docker run --rm -v `pwd`:/mnt koalaman/shellcheck:stable bin/*

test:
	docker run --rm -v `pwd`/nginx/settings/nginx:/etc/nginx:ro yandex/gixy /etc/nginx/nginx.conf
	docker run -it --rm -v `pwd`/home-assistant/settings:/config:ro homeassistant/amd64-homeassistant hass -c /config --script check_config
	for file in $(find esphome -type f -name "*.yaml" -not -name "secrets.yaml"); do docker run --rm -v "${PWD}/esphome":/config -it esphome/esphome master_bedroom_salt_lamp.yaml config; done
