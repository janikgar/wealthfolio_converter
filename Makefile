.PHONY: testall
testall: lint sast test

lint:
	mypy .
	pylint *.py

test:
	pytest

sast:
	bandit -c pyproject.toml -r .

run_local:
	fastapi dev wealthfolio_converter/api/main.py

build:
	docker build -t wf_converter:latest .

run:
	docker run -it --rm --publish 8000:8000 --name wfc localhost/wf_converter:latest