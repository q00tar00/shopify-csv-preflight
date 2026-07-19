# Shopify Product CSV 検査ルール v1 仕様

> 本書は CSV Preflight Validator の検査ルールの SoT。実装（`src/preflight_kit/`）とテスト期待値の根拠になる。
> 設計の SoT は `docs/superpowers/specs/2026-06-22-csv-preflight-validator-design.md`。
> 出典: Shopify 公式「Using CSV files to import and export products」
> https://help.shopify.com/en/manual/products/import-export/using-csv

## スコープ

- 対象は **product CSV のみ**。order/customer CSV（買い手 PII）は処理しない（PII らしい列名検出で停止）。
- Admin API 不要・ストア非書き込み・ファイル処理のみ。
- 自動修正は **両義のない機械的変換（`fix_class=proven` かつ `auto_fixable=True`）のみ** CSV に反映する。
  判断を要する変換は警告（`suggested`）止まりで CSV に反映しない。

---

## 1. canonical 列リスト（全列）

Shopify の product CSV は時期により **新形式ヘッダー**（例 `URL handle`）と **旧形式 alias**（例 `Handle`）が
混在する。検査では両方を canonical key に正規化して解釈する。`CANONICAL_TO_HEADERS`
（`src/preflight_kit/header_registry.py`）の SoT は本表。各行の先頭ヘッダーが「現行公式の正式名（primary）」で、
case-only 修正（F03a・proven）の正規化先になる。2つ目以降は旧形式 alias（F03b・suggested）。

| canonical key | 新形式ヘッダー（primary） | 旧形式 alias |
| --- | --- | --- |
| `handle` | URL handle | Handle |
| `title` | Title | — |
| `description` | Description | Body (HTML) |
| `vendor` | Vendor | — |
| `product_category` | Product category | Product Category |
| `type` | Type | — |
| `tags` | Tags | — |
| `published` | Published on online store | Published |
| `status` | Status | — |
| `sku` | SKU | Variant SKU |
| `barcode` | Barcode | Variant Barcode |
| `option1_name` | Option1 name | Option1 Name |
| `option1_value` | Option1 value | Option1 Value |
| `option1_linkedto` | Option1 LinkedTo | Option1 Linked To |
| `option2_name` | Option2 name | Option2 Name |
| `option2_value` | Option2 value | Option2 Value |
| `option2_linkedto` | Option2 LinkedTo | Option2 Linked To |
| `option3_name` | Option3 name | Option3 Name |
| `option3_value` | Option3 value | Option3 Value |
| `option3_linkedto` | Option3 LinkedTo | Option3 Linked To |
| `price` | Price | Variant Price |
| `compare_at_price` | Compare-at price | Variant Compare At Price |
| `cost_per_item` | Cost per item | Cost per item (USD) |
| `inventory_tracker` | Inventory tracker | Variant Inventory Tracker |
| `inventory_qty` | Inventory quantity | Variant Inventory Qty |
| `inventory_policy` | Continue selling when out of stock | Variant Inventory Policy |
| `fulfillment_service` | Fulfillment service | Variant Fulfillment Service |
| `weight_value` | Weight value (grams) | Variant Grams |
| `weight_unit` | Weight unit for display | Variant Weight Unit |
| `requires_shipping` | Requires shipping | Variant Requires Shipping |
| `charge_tax` | Charge tax | Variant Taxable |
| `gift_card` | Gift card | Gift Card |
| `image_src` | Product image URL | Image Src |
| `image_position` | Image position | Image Position |
| `variant_image` | Variant image URL | Variant Image |
| `image_alt` | Image alt text | Image Alt Text |
| `seo_title` | SEO title | SEO Title |
| `seo_description` | SEO description | SEO Description |
| `collection` | Collection | — |

> 実装注意: 本表に無い現行公式列があれば registry と本表の双方に追加する。怠ると F03d が
> 有効な公式列を unknown warning として誤検出する。

### 動的（dynamic）列パターン — 列挙不能・誤検出も誤変換もしない

以下は market 名・metafield namespace 等が可変で列挙できない。`match_kind` が `dynamic` /
`variant_metafield` を返し、F03d（unknown）の対象から除外する。

| 種別 | パターン | match_kind | 扱い |
| --- | --- | --- | --- |
| product metafield（接頭辞） | `Metafield: <ns>.<key> [type]` | dynamic | 警告しない |
| product metafield（bare） | `product.metafields.<ns>.<key>` | dynamic | 警告しない |
| Google Shopping | `Google Shopping / ...` | dynamic | 警告しない |
| Markets 価格（market 可変） | `Price / <market>`, `Compare-at price / <market>` | dynamic | 警告しない |
| Markets included | `Included / <market>` | dynamic | 警告しない |
| variant metafield（接頭辞） | `Variant Metafield: <ns>.<key> [type]` | variant_metafield | F03e 警告（標準 import 非対応） |
| variant metafield（bare） | `variant.metafields.<ns>.<key>` | variant_metafield | F03e 警告 |

> variant metafield は dynamic より先に判定し dynamic から除外する（標準 product CSV import が
> 非対応なので警告を出すため）。

---

## 2. row_kind 判定基準

各データ行を `product` / `variant` / `image` のいずれかに分類する。判定は loader が行う。

- **product**: グループ先頭行（`is_product_start=True`）。
- **image**: `is_product_start=False` かつ **Title 空** かつ **image_src 系のみ埋まり** option/sku/price が空の行。
- **variant**: 上記いずれでもない継続行（option 値・sku・price のいずれかが埋まる）。

判定の優先順位（重要）:

1. `is_product_start` なら無条件で `product`。
2. それ以外で「Title 空 ∧ image_src あり ∧ option/sku/price 全空」なら `image`（**variant より先に評価**）。
3. 残りは `variant`。

### product-start 判定（grouping）

`handle` 列と `Title` を基準に4分岐で判定する。比較対象は「直前行の生 handle」ではなく
**グループ代表 handle**（最後に product-start を立てた行の handle 値）。これにより handle 空の本体行を
挟んでも後続の同一 handle 行が誤って前グループを継承する carry-over を防ぐ。

| 状況 | product-start? | 理由 |
| --- | --- | --- |
| handle 非空 ∧ グループ代表 handle と異なる | Yes | 新グループ |
| handle 非空 ∧ 代表 handle と同一 ∧ Title 非空 | Yes | 2つ目の本体行（R03 が重複検知） |
| handle 非空 ∧ 代表 handle と同一 ∧ Title 空 | No | 正常な variant/image 反復 |
| handle 空 ∧ Title 非空 | Yes | 本体行で handle 値だけ欠落（R02 が intent 別に判定） |
| handle 空 ∧ Title 空 ∧ 直前にグループあり | No | 親 handle を書き忘れた variant/image 継続行（R02 が critical） |
| handle 空 ∧ Title 空 ∧ 直前グループなし | Yes | 先頭行 |

---

## 3. 必須欄マトリクス（行種別 × import_intent → severity）

import 後の挙動が intent（new / update / mixed）で変わる欄の severity を確定する。

| 検査 | rule_id | 行種別 | new | update | mixed |
| --- | --- | --- | --- | --- | --- |
| Title 欠落 | R01 | product-start | critical | critical | warning |
| Title 空 | R01 | variant / image | (検査せず) | (検査せず) | (検査せず) |
| handle 欠落 | R02 | product-start | warning | critical | warning |
| handle 欠落（親継承） | R02 | variant / image | critical | critical | critical |

- **R01**: product-start 行の Title は商品作成に必須。new/update では無いと作成/更新できず critical。
  mixed は片方が update のケースを含むため warning に緩める。variant/image 行の Title 空は正常なので検査しない。
- **R02**: handle は update で既存商品を特定する鍵。product-start で欠けると update 不能 → update=critical、
  new/mixed=warning。variant/image 行で親 handle が欠けると**どの商品の variant か特定不能**なので
  全 intent で critical。

---

## 4. 全ルール（id / severity / fix_class / message テンプレ）

### File / 構造ルール（F01-F04）

| rule_id | 検査内容 | severity | fix_class | 担当 | ja message | en message |
| --- | --- | --- | --- | --- | --- | --- |
| F01a | UTF-8 BOM がファイル先頭にある | critical | proven | loader | UTF-8 BOM がファイル先頭にあります。 | UTF-8 BOM detected at file start. |
| F01b | UTF-8 デコード不能（推定変換しない） | critical | suggested | loader | ファイルが正しい UTF-8 ではありません（エンコーディング推定が必要）。 | File is not valid UTF-8 (encoding guess required). |
| F01c | 制御文字を含む | warning | none | F01c | 列 '{col}' に制御文字があります。 | Control character in column '{col}'. |
| F02 | スマートクォート（弯曲引用符） | warning | suggested | F02 | 列 '{col}' にスマートクォートがあります。 | Smart/curly quotes in column '{col}'. |
| F03a | ヘッダーが既知列と大小違いのみ（primary 限定） | critical | proven | F03a | ヘッダー '{col}' は既知列と大小文字だけ異なります。 | Header '{col}' differs only by case from a known column. |
| F03b | ヘッダーが旧形式 alias | warning | suggested | F03b | ヘッダー '{col}' は旧形式 alias です。 | Header '{col}' is a legacy alias. |
| F03c | 必須 canonical 列（title/handle）が無い | critical | none | F03c | '{key}' に対応する必須列がありません。 | Required column for '{key}' is missing. |
| F03d | 未知列（typo の疑い） | warning | none | F03d | 未知の列 '{col}'（typo の可能性）。 | Unknown column '{col}' (possible typo). |
| F03e | variant metafield 列（標準 import 非対応） | warning | none | F03e | variant metafield 列 '{col}' は標準 product CSV import で非対応です。 | Variant metafield column '{col}' is not supported by standard product CSV import. |
| F04a | ファイルが 15MB 超 | critical | none | F04a | ファイルが {n} バイトで 15MB 制限を超えています。 | File is {n} bytes, over the 15MB Shopify import limit. |
| F04b | 行数が 5000 超 | warning | none | F04b | ファイルが {n} 行あります。分割を検討してください。 | File has {n} rows; consider splitting for reliability. |
| F04c | 行のセル数がヘッダー列数を超過（列ずれ） | critical | none | loader | {line} 行目はセルが {got} 個でヘッダー列数 {want} を超えています（列ずれ）。 | Row {line} has {got} cells, more than the {want} header columns (column misalignment). |

> 注: F01a/F01b/F04c は loader が出す。F01c-F04b はルール関数。
> PII 列検出は `GUARD-PII`（critical / none）で処理を停止する（マトリクス外の安全ガード）。

### 行ルール（R01-R14）

| rule_id | 検査内容 | severity | fix_class | en message（要旨） |
| --- | --- | --- | --- | --- |
| R01 | product-start の Title 欠落 | §3 マトリクス | none | Product-start row is missing Title. |
| R02 | handle 欠落（product-start / variant 親継承） | §3 マトリクス | none | Missing URL handle. |
| R03 | 同一 handle に複数 product-start（サイレント上書き） | critical | none | N product-start rows share handle '{h}'. |
| R04 | グループ内 Option 組み合わせ重複 | critical | none | Duplicate option combination within product group. |
| R05 | Option1 dependency 違反（name/value 片欠け・Option2 先行） | critical | none | Fix option name/value pairing. |
| R06 | SKU 空欄 / グループ跨ぎ重複 / 危険文字 | warning | none | SKU empty / reused / contains breaking chars. |
| R07 | inventory_policy が許容値外（deny/continue） | warning | suggested | inventory_policy is not a documented value. |
| R08 | inventory_tracker ありで qty 空/非数値 | warning | none | Tracker set but quantity empty/non-numeric. |
| R09 | fulfillment_service 空欄（manual 既定） | warning | none | Fulfillment service is empty (defaults to manual). |
| R10 | 価格が非数値/負数 / compare-at ≤ price | warning | none | Price not numeric/negative or compare-at ≤ price. |
| R11 | image alt 有 but image_src 空 | critical | none | Image alt text present but image URL is empty. |
| R12 | image_src に http(s) scheme 無（ローカルパス等） | warning | none | Image URL has no http(s) scheme. |
| R13 | SKU が Excel 科学表記 | warning | none | SKU looks like Excel scientific notation. |
| R14 | product-start で Option2 有 but Option1 無（位置ずれ疑い） | warning | none | Option2 set without Option1 (possible position shift). |

> R07 は SoT 未確定のため proven に昇格しない（warning + suggested 止まり）。
> suggested_fix テンプレは各ルール実装（`rules/file_rules.py` / `rules/row_rules.py`）を SoT とする。

---

## 5. 合否判定の表現（限定的・断定しない）

- critical 0 件のとき: `No blocking findings detected within implemented checks`
  と表現し、「import 可能」とは**断定しない**。未検査範囲を必ず併記する。
- critical あり: import 前に解消を促す。「import 可能は保証しない」と明記する。
- **未検査範囲（必ず report に明記）**: 画像 URL の公開到達性 / 既存ストアとの handle overwrite・ignore /
  metafield product reference の解決 / 既存商品との option 位置整合。
