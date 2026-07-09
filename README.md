# Shopify Product CSV Preflight Validator

Check your Shopify **product** CSV *before* you upload it. Runs locally on your machine,
never touches your store, needs no API key. A file goes in; a verdict comes out.

GitHub repo: https://github.com/q00tar00/shopify-csv-preflight

**Try it in your browser:** https://shopify-7mc.pages.dev/ — no upload, no login, your CSV never leaves the page.

See a real run: [example report](examples/reports/csv-preflight-messy-report.md) from a deliberately messy sample CSV.

> **Status:** CLI MVP. Self-serve, local-only, file-processing tool. No Admin API, no store
> writes, no account. Product CSV only — it refuses files that look like order/customer exports.

## What it does

You exported a product CSV, edited it in Excel or Google Sheets, and uploaded it to Shopify.
Shopify's import is a two-stage process (validate, then apply), so a file can pass the upload
dialog and still misbehave: a handle gets overwritten, a variant attaches to the wrong product,
half your rows go missing — and you find out days later from a customer.

This tool catches the import-breaking mistakes first. For one run it produces three files:

- `fixed_products.csv` — a safe copy with the unambiguous, mechanical mistakes already corrected.
- `errors.csv` — a machine-readable list of every finding (row, rule, severity, suggested fix).
- `report.md` — a human-readable report you can read in 30 seconds.

It **auto-fixes only what is unambiguous** (UTF-8 BOM, header case). Every judgment call —
missing/duplicate handles, negative prices, image/alt mismatches — is *reported, never silently
rewritten*. Every report ends with a **Not checked** section, because a file-only tool can't
verify live-store behavior and won't pretend otherwise.

## Install

Requires Python 3.11+. Using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install csv-preflight
csv-preflight check your-products.csv --out-dir ./out
```

Or run it without installing:

```bash
uvx csv-preflight check your-products.csv --out-dir ./out
```

## Usage

```bash
csv-preflight check products.csv --out-dir ./out --lang en
```

Options:

- `--out-dir DIR` — where to write `fixed_products.csv` / `errors.csv` / `report.md`.
- `--lang en|ja` — report language.
- `--no-fix` — report only; do not write `fixed_products.csv`.
- `--intent create|update` — context for handle-overwrite warnings.

The exit code is non-zero when criticals are present, so you can wire it into a script and
stop a bad upload automatically.

See a real run on a deliberately messy file under [`examples/`](examples/): inputs in
[`examples/inputs/`](examples/inputs/), sample outputs in [`examples/reports/`](examples/reports/).

## What it checks (v1)

File-level structure (encoding, BOM, headers, size limits) plus per-row rules covering missing /
duplicate handles, variant parent linkage, price sanity (negative, compare-at below price),
image/alt-text consistency, and inventory fields. Full spec:
[`docs/shopify-product-csv-rules.md`](docs/shopify-product-csv-rules.md).

## Privacy

It reads a file. It does not touch your store. Your catalog never leaves your machine.
The tool detects buyer-PII column names (order/customer exports) and **refuses** those files —
your buyers' personal data never goes through it.

## Documents

- Inspection rules v1: [`docs/shopify-product-csv-rules.md`](docs/shopify-product-csv-rules.md)

## Feedback

This is an early MVP and I'm validating whether merchants find it useful. If a silent partial
import has ever bitten you, please open an issue with what broke — that's exactly the signal I'm
looking for.

## License

Source-available — see [`LICENSE`](LICENSE). You may read the source and evaluate the tool for
personal use; commercial use and redistribution require permission.
