from __future__ import annotations
import re

# canonical key -> [新形式ヘッダー, 旧形式 alias...]（先頭が canonical 正式名）
CANONICAL_TO_HEADERS: dict[str, list[str]] = {
    "handle": ["URL handle", "Handle"],
    "title": ["Title"],
    "description": ["Description", "Body (HTML)"],
    "vendor": ["Vendor"],
    "product_category": ["Product category", "Product Category"],
    "type": ["Type"],
    "tags": ["Tags"],
    "published": ["Published on online store", "Published"],
    "status": ["Status"],
    "sku": ["SKU", "Variant SKU"],
    "barcode": ["Barcode", "Variant Barcode"],
    "option1_name": ["Option1 name", "Option1 Name"],
    "option1_value": ["Option1 value", "Option1 Value"],
    "option1_linkedto": ["Option1 LinkedTo", "Option1 Linked To"],
    "option2_name": ["Option2 name", "Option2 Name"],
    "option2_value": ["Option2 value", "Option2 Value"],
    "option2_linkedto": ["Option2 LinkedTo", "Option2 Linked To"],
    "option3_name": ["Option3 name", "Option3 Name"],
    "option3_value": ["Option3 value", "Option3 Value"],
    "option3_linkedto": ["Option3 LinkedTo", "Option3 Linked To"],
    "price": ["Price", "Variant Price"],
    "compare_at_price": ["Compare-at price", "Variant Compare At Price"],
    "cost_per_item": ["Cost per item", "Cost per item (USD)"],
    "inventory_tracker": ["Inventory tracker", "Variant Inventory Tracker"],
    "inventory_qty": ["Inventory quantity", "Variant Inventory Qty"],
    "inventory_policy": [
        "Continue selling when out of stock",
        "Variant Inventory Policy",
    ],
    "fulfillment_service": ["Fulfillment service", "Variant Fulfillment Service"],
    "weight_value": ["Weight value (grams)", "Variant Grams"],
    "weight_unit": ["Weight unit for display", "Variant Weight Unit"],
    "requires_shipping": ["Requires shipping", "Variant Requires Shipping"],
    "charge_tax": ["Charge tax", "Variant Taxable"],
    "gift_card": ["Gift card", "Gift Card"],
    "image_src": ["Product image URL", "Image Src"],
    "image_position": ["Image position", "Image Position"],
    "variant_image": ["Variant image URL", "Variant Image"],
    "image_alt": ["Image alt text", "Image Alt Text"],
    "seo_title": ["SEO title", "SEO Title"],
    "seo_description": ["SEO description", "SEO Description"],
    "collection": ["Collection"],
}

# 注意（実装者向け）: 上表は repo sample + spec 必須列 + 現行公式 CSV の主要列を含むが、
# Task 1（rules spec）で公式 current CSV 全列を確定し、ここに無い現行列があれば必ず追加する。
# 出典: https://help.shopify.com/en/manual/products/import-export/using-csv
# 怠ると F03d が有効な公式列を unknown warning として誤検出する（round-3 #1 の根本対策）。

# 元ヘッダー(lower) -> canonical key
_HEADER_LOWER_TO_KEY: dict[str, str] = {}
# 元ヘッダー(正確) -> canonical key
_HEADER_EXACT_TO_KEY: dict[str, str] = {}
# canonical 正式名(新形式)の集合（先頭要素）
_CANONICAL_PRIMARY: set[str] = set()
# canonical 正式名(新形式)の lower -> primary（case-only 判定を primary に限定する。
# alias の大小違いを case_only と誤判定して proven 改名するのを防ぐ・round-3 #2）
_PRIMARY_LOWER_TO_KEY: dict[str, str] = {}
for _key, _headers in CANONICAL_TO_HEADERS.items():
    _primary = _headers[0]
    _CANONICAL_PRIMARY.add(_primary)
    _PRIMARY_LOWER_TO_KEY[_primary.lower()] = _key
    for _i, _h in enumerate(_headers):
        _HEADER_EXACT_TO_KEY[_h] = _key
        _HEADER_LOWER_TO_KEY[_h.lower()] = _key

# dynamic 列パターン（registry に列挙不能な可変ヘッダー。誤検出も誤変換もしない）。
# round-4 #1: Markets 価格列の market 名は可変（International だけでない）。
# product metafield は `Metafield:` 接頭辞 / `(...product.metafields...)` / bare
# `product.metafields.<ns>.<key>` の3形式がある。variant metafield は除外する。
_DYNAMIC_PATTERNS = [
    re.compile(r"^Metafield:", re.IGNORECASE),
    re.compile(r"product\.metafields\.", re.IGNORECASE),  # 括弧付き/ bare 両対応
    re.compile(r"^Google Shopping", re.IGNORECASE),
    # Markets/地域別価格: "Price / <market>" "Compare-at price / <market>"（market 名可変）
    re.compile(r"^(Price|Compare-at price)\s*/\s*.+", re.IGNORECASE),
    re.compile(r"\bIncluded\b\s*/\s*.+", re.IGNORECASE),  # Markets included / <market>
]
# variant metafield: `Variant Metafield:` 接頭辞 / bare `variant.metafields.<ns>.<key>`。
# dynamic より先に判定し dynamic から除外する（standard product CSV import 非対応のため警告）。
_VARIANT_METAFIELD = re.compile(
    r"^Variant Metafield:|variant\.metafields\.", re.IGNORECASE
)


def to_canonical(header: str) -> str | None:
    if header in _HEADER_EXACT_TO_KEY:
        return _HEADER_EXACT_TO_KEY[header]
    return _HEADER_LOWER_TO_KEY.get(header.lower())


def is_variant_metafield(header: str) -> bool:
    # `^Variant Metafield:` か bare `variant.metafields.` を拾う（search で両対応）。
    return bool(_VARIANT_METAFIELD.search(header))


def is_dynamic(header: str) -> bool:
    if is_variant_metafield(header):
        return False
    return any(p.search(header) for p in _DYNAMIC_PATTERNS)


def match_kind(header: str) -> str:
    if header in _CANONICAL_PRIMARY:
        return "canonical"
    key = _HEADER_EXACT_TO_KEY.get(header)
    if key is not None:
        # 完全一致だが正式名でない = 旧形式 alias（exact 一致）
        return "alias"
    # case_only は **現行 primary ヘッダーの大小違いのみ**。これは proven 改名対象。
    if header.lower() in _PRIMARY_LOWER_TO_KEY:
        return "case_only"
    # primary でない lower 一致 = alias の大小違い。alias→canonical 改名は suggested の
    # ため proven 化しない。alias 扱いに倒す（F03b が suggested で提案・改名しない）。
    if header.lower() in _HEADER_LOWER_TO_KEY:
        return "alias"
    if is_variant_metafield(header):
        return "variant_metafield"
    if is_dynamic(header):
        return "dynamic"
    return "unknown"
