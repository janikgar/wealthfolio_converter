wealthfolio_converter
---
![Tests](badges/tests.svg)
![Coverage](badges/coverage.svg)
![Last Run](badges/last-run.svg)
![Duration](badges/duration.svg)
![Skipped](badges/skipped.svg)
![Warnings](badges/warnings.svg)

This Python project converts CSV flat files (and some XLSX versions) into a standardized, vendor-neutral format that can be imported into Wealthfolio.

## Getting started
1. Install `uv`
2. Run `uv sync` to install dependencies
3. Enter the virtualenv with `source .venv/bin/activate`

### CLI Usage
```
usage: wf_converter.py [-h] --format {fidelity,vanguard,vanguard-xlsx,trowe} --output OUTPUT input
wf_converter.py: error: the following arguments are required: --format/-f, --output/-o, input
```

### API Usage
Can also be run as a simple FastAPI app to receive S3-compatible webhook events.
```
fastapi dev wealthfolio_converter/api/main.py
# OR
make run_local
```  

## Vendor adapters
- Fidelity
- T. Rowe Price
- Vanguard (CSV and XLSX)

## S3 Connectivity
S3 can be used for input and output. Currently, this is configured to a local configuration with SILO, but uses Boto3 (and so should be compatible with any S3-compatible API).

## Testing
Make can be run to execute test suites.
- `make lint` - run Pylint
- `make sast` - run Bandit static code analysis
- `make test` - run full Pytest unit test suites
- `make testall` - run all tests above
- `make run_local` - run dev server in current virtual environment
- `make build` - build Docker container
- `make run` - run Docker container
 