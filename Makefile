.PHONY: testall scanall
testall: lint test # lint type checks and unit tests

scanall: sast vulns # static analysis and vuln checks

lint: # type checking and general python linting
	mypy src/
	pylint src/**/*.py

test: # unit tests
	pytest

sast: # static analysis
	bandit -c pyproject.toml -r src/

run_local: # local dev
	fastapi dev --host 0.0.0.0 src/wealthfolio_converter/api/main.py

build: # docker image build
	docker build -t localhost/wf_converter:latest .

run: # run docker image
	docker run -it --rm --publish 8000:8000 --name wfc localhost/wf_converter:latest

vulns: # check for vulns
	docker run --rm --name wf_scan -v trivy:/cache -v .:/repo aquasec/trivy:0.76.1 repository --cache-dir /cache --ignore-unfixed --scanners vuln --ignorefile /repo/.trivyignore.yaml .

push_version: # tag and push a new version
	git tag v$$(uv version --short --no-color)
	git push origin v$$(uv version --short --no-color)

help: # see make options
	@egrep '^\w+:' Makefile | column -t -s#
