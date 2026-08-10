wealthfolio_converter
---

This Python project converts CSV flat files (and some XLSX versions) into a standardized, vendor-neutral format that can be imported into Wealthfolio.

## Vendor adapters
- Fidelity
- T. Rowe Price
- Vanguard (CSV and XLSX)

## S3 Connectivity
S3 can be used for input and output. Currently, this is configured to a local configuration with SILO, but uses Boto3 (and so should be compatible with any S3-compatible API).
 