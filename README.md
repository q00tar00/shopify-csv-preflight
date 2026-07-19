# Shopify Product CSV Preflight Validator

[![PyPI version](https://img.shields.io/pypi/v/csv-preflight.svg)](https://pypi.org/project/csv-preflight/)
[![Source-available license](https://img.shields.io/badge/license-source--available-blue.svg)](LICENSE)
[![CI](https://github.com/q00tar00/shopify-csv-preflight/actions/workflows/ci.yml/badge.svg)](https://github.com/q00tar00/shopify-csv-preflight/actions/workflows/ci.yml)

Validate a Shopify **product** CSV before uploading it. `csv-preflight` runs locally, never connects to a Shopify store, and needs no API key. It reports import-risk findings and produces reviewable output files without changing the input CSV.

> **Status:** Beta CLI, version 0.1.0. This is a local, file-processing tool for product CSVs only. It has no Admin API integration, store-write capability, or user account system.

## Project links

- Web checker: [shopify-7mc.pages.dev](https://shopify-7mc.pages.dev/) (no upload or login)
- Package: [PyPI — csv-preflight](https://pypi.org/project/csv-preflight/)
- Source and issue tracker: [q00tar00/shopify-csv-preflight](https://github.com/q00tar00/shopify-csv-preflight)
- Change history: [CHANGELOG.md](CHANGELOG.md)

## What it checks

The validator checks Shopify product-CSV structure and row-level risks, including:

- UTF-8 encoding, BOMs, control characters, headers, file size, and column alignment.
- Missing or duplicate product handles, required-column gaps, and variant parent linkage.
- Duplicate option combinations and option dependency or position problems.
- SKU gaps, reused SKUs, and Excel-style scientific notation.
- Inventory, fulfillment, price, image URL, and image-alt-text consistency.
- Product CSVs that appear to be order or customer exports: these are refused before row-level processing to avoid handling buyer PII.

It supports current Shopify product-CSV headers and documented legacy aliases. The complete, versioned rule reference is [docs/shopify-product-csv-rules.md](docs/shopify-product-csv-rules.md).

## Install

Requires Python 3.11 or later.

With [uv](https://docs.astral.sh/uv/):

```bash
uv tool install csv-preflight
```

With pip:

```bash
python -m pip install csv-preflight
```

## Usage

```bash
csv-preflight check products.csv --out-dir ./out --lang en --intent new
```

Each run writes the following to `--out-dir`:

- `fixed_products.csv` — a copy with only unambiguous mechanical fixes applied (currently UTF-8 BOM removal and case-only header normalization).
- `errors.csv` — machine-readable findings with row, rule, severity, and suggested-fix fields.
- `report.md` — a human-readable summary.

Useful options:

- `--out-dir DIR` — output directory (default: `./out`).
- `--lang en|ja` — report language (default: `ja`).
- `--no-fix` — report findings without writing `fixed_products.csv`.
- `--intent new|update|mixed` — choose the import context used for handle and title severity.

The command exits with status `1` when it finds a critical issue; otherwise it exits with `0`. A zero exit status means no critical finding was detected within the implemented checks, not that Shopify will necessarily accept or apply the import as intended.

For a reproducible example, see the [deliberately messy sample report](examples/reports/csv-preflight-messy-report.md) and its [input CSV](examples/inputs/messy-product-import-sample.csv).

## Boundaries and privacy

The CLI reads a local file and does not upload it or access a Shopify store. It does not verify live-store behavior. In particular, it cannot check image URL reachability, conflicts with existing store handles, metafield product-reference resolution, or option-position consistency with existing products; every report identifies these limits.

Auto-fixes are deliberately limited to proven, unambiguous transformations. Findings that require a business decision are reported but not silently rewritten.

## Documentation

- [Inspection rules](docs/shopify-product-csv-rules.md)
- [Change history](CHANGELOG.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Maintenance and support

This project is maintained by the GitHub user [q00tar00](https://github.com/q00tar00). The public GitHub repository and its issue tracker are the project’s canonical communication channels.

For questions, bug reports, feature requests, or examples of a product-CSV import that went wrong, use [GitHub Issues](https://github.com/q00tar00/shopify-csv-preflight/issues). Please use a small redacted reproduction and never post customer, order, access-token, or other sensitive data. Support is provided on a best-effort basis; no response-time commitment is made.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the supported scope, local setup, test command, and pull-request expectations.

## Security

Please follow [SECURITY.md](SECURITY.md) for vulnerability reporting. Do not disclose exploitable security details or sensitive CSV data in a public issue.

## License

This project is source-available, not open source. See [LICENSE](LICENSE) for permitted use and redistribution terms.
