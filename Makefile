clean:
	pipenv --rm
init:
	pip3 install --upgrade pip pipenv
	pipenv lock
	pipenv install --three --dev
	pipenv run pre-commit install
lint:
	pipenv run flake8 appdaemon/settings/apps
	pipenv run pydocstyle appdaemon/settings/apps
	pipenv run pylint appdaemon/settings/apps
	pipenv run mypy --ignore-missing-imports appdaemon/settings/apps
