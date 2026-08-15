.PHONY: testall
testall: lint sast test

lint:
	mypy .
	pylint *.py

test:
	pytest

sast:
	bandit -c pyproject.toml -r .
