# Contributing to Shopify Product CSV Preflight

Thanks for helping improve `csv-preflight`. This project validates Shopify product CSV files before import; changes should preserve its local-only, non-destructive design.

## Before opening an issue

- Use [GitHub Issues](https://github.com/q00tar00/shopify-csv-preflight/issues) for bugs, feature requests, questions, and product-CSV import stories.
- Do not attach real customer or order exports, access tokens, or other sensitive data. Provide a minimal, redacted CSV reproduction instead.
- Check the [rule reference](docs/shopify-product-csv-rules.md) before reporting an expected rule outcome.

## Development setup

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/q00tar00/shopify-csv-preflight.git
cd shopify-csv-preflight
uv sync --extra dev
uv run pytest
```

Run the CLI against a sample file with:

```bash
uv run csv-preflight check examples/inputs/shopify-product-import-sample.csv --out-dir ./out --lang en --intent new
```

The generated `out/` directory is local output and should not be committed.

## Pull requests

- Keep pull requests focused and explain the user-visible validation or documentation change.
- Add or update tests for changes to validation, report, or auto-fix behavior.
- Preserve the distinction between proven auto-fixes and findings that need user judgment.
- Keep documentation in English and update the rule reference when a rule’s behavior changes.
- Do not add store access, API calls, or data-upload behavior without an explicit design discussion first.
- Confirm `uv run pytest` passes before requesting review.

## Scope and review

The maintainer, [q00tar00](https://github.com/q00tar00), reviews contributions on a best-effort basis. Issues and pull requests should be respectful, reproducible, and limited to Shopify product-CSV preflight validation or its documentation and tooling.
