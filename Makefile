ci:
	pipenv run gixy nginx/settings/nginx/*.conf nginx/settings/nginx/conf.d/*
init:
	pip install --upgrade pip pipenv
	pipenv lock
	pipenv install --dev
lint:
	pipenv run flake8 appdaemon/settings
	pipenv run jsonlint dasher/settings/config.json
	pipenv run pydocstyle appdaemon/settings
	pipenv run pylint --disable=import-error,no-name-in-module,too-few-public-methods appdaemon/settings
	pipenv run yamllint appdaemon/settings ha-dockermon/settings home-assistant/settings
