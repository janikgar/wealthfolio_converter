wealthfolio_converter
---

This Python project converts CSV flat files (and some XLSX versions) into a standardized, vendor-neutral format that can be imported into Wealthfolio.

## Getting started
1. Install `uv`
2. Run `uv sync` to install dependencies
3. Enter the virtualenv with `source .venv/bin/activate`

### Usage


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
 