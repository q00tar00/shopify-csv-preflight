# Shopify CSV Preflight Report

- Summary: scanned rows 4 / product groups 3 / 6 critical / 8 warning / 2 auto-fixed (proven) / 1 suggested

## Critical (fix before import)
- [F01a] file: UTF-8 BOM detected at file start.
- [F03a] file: Header 'title' differs only by case from a known column.
- [R02] row 2: Variant/image row is missing the parent URL handle.
- [R03] row 1: 2 product-start rows share handle 'aurora-hoodie' (rows 1, 3).
- [R03] row 3: 2 product-start rows share handle 'aurora-hoodie' (rows 1, 3).
- [R11] row 4: Image alt text present but image URL is empty.

## Warning (review recommended)
- [R07] row 4: inventory_policy 'maybe' is not a documented value (deny/continue).
- [R08] row 4: Inventory tracker 'shopify' set but inventory quantity is empty/non-numeric.
- [R09] row 1: Fulfillment service is empty (defaults to manual).
- [R09] row 2: Fulfillment service is empty (defaults to manual).
- [R09] row 3: Fulfillment service is empty (defaults to manual).
- [R09] row 4: Fulfillment service is empty (defaults to manual).
- [R10] row 1: Compare-at price 3900.0 <= price 4800.0.
- [R10] row 4: Price '-1800' is negative.

## Auto-fixed (proven)
- [F01a] file: UTF-8 BOM detected at file start.
- [F03a] file: Header 'title' differs only by case from a known column.

## Suggested (not applied to CSV)
- [R07] row 4: inventory_policy 'maybe' is not a documented value (deny/continue).

## Not checked
- Not checked by this tool: image URL public reachability, handle overwrite/ignore against an existing store, metafield product reference resolution, and option position consistency with existing products.

## Next actions
- Critical findings present. Resolve before import. Import is not guaranteed.
