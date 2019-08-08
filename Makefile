clean:
	pipenv --rm
init:
	pip3 install --upgrade pip pipenv
	pipenv lock
	pipenv install --three --dev
	pipenv run pre-commit install
lint:
	pipenv run flake8 appdaemon/settings/apps
	pipenv run mypy --ignore-missing-imports appdaemon/settings/apps
	pipenv run pylint --rcfile appdaemon/settings/pylintrc appdaemon/settings/apps
	pipenv run yamllint home-assistant/settings/
test:
	docker run --rm -v `pwd`/nginx/settings/nginx:/etc/nginx yandex/gixy /etc/nginx/nginx.conf
