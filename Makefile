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
	docker pull yandex/gixy:latest
	docker run --rm -v `pwd`/nginx/settings/nginx:/etc/nginx:ro yandex/gixy /etc/nginx/nginx.conf

	docker pull homeassistant/amd64-homeassistant:latest
	docker run -it --rm -v `pwd`/home-assistant/settings:/config:ro homeassistant/home-assistant:latest python -m homeassistant -c /config --script check_config

	docker pull esphome/esphome:latest
	for file in $(find esphome -type f -name "*.yaml" -not -name "secrets.yaml"); do docker run --rm -v "${PWD}/esphome":/config -it esphome/esphome "$file" config; done
