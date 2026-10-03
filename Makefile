.PHONY: testall scanall
testall: lint test

scanall: sast vulns

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
	docker build -t localhost/wf_converter:latest .

run:
	docker run -it --rm --publish 8000:8000 --name wfc localhost/wf_converter:latest

vulns:
	docker run -v trivy:/cache -v .:/repo aquasec/trivy:0.75.0 repository --cache-dir /cache --ignore-unfixed --scanners vuln --ignorefile /repo/.trivyignore.yaml .

push_version:
	git tag $$(uv version --short --no-color)
	git push origin $$(uv version --short --no-color)

help:
	egrep '^\w+:' Makefile