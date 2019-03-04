ci:
	pipenv run gixy nginx/settings/nginx/*.conf nginx/settings/nginx/conf.d/*
clean:
	pipenv --rm
init:
	pip3 install --upgrade pip pipenv
	pipenv lock
	pipenv install --dev
lint:
	pipenv run flake8 appdaemon/settings bin/enabled_toggles
	pipenv run pydocstyle appdaemon/settings bin/enabled_toggles
	pipenv run pylint --disable=import-error,no-name-in-module,too-few-public-methods appdaemon/settings bin/enabled_toggles
	pipenv run yamllint amazon-dash/settings appdaemon/settings home-assistant/settings
