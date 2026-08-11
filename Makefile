.PHONY: testall
testall: lint sast test

lint:
	pylint *.py

test:
	pytest

sast:
	bandit -c pyproject.toml -r .
