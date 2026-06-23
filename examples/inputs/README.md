# Example input files

Sample Shopify **product** CSV files for trying the validator. No buyer/customer PII is included.

- `shopify-product-import-sample.csv` — a clean, well-formed product import (passes with no criticals).
- `messy-product-import-sample.csv` — a deliberately broken export that triggers several findings:
  UTF-8 BOM, header case drift, a variant row missing its parent handle, two products sharing one
  handle, image alt text with no image URL, a negative price, and a compare-at price below the price.

Run the validator against either one:

```bash
csv-preflight check messy-product-import-sample.csv --out-dir ./out --lang en
```

The generated `report.md` / `errors.csv` for the messy file are committed under
[`../reports/`](../reports/) so you can see the expected output without running anything.
