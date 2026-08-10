lint:
	pylint *.py

test:
	pytest

sast:
	bandit -c pyproject.toml -r .

testall: lint sast test