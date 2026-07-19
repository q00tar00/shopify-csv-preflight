from preflight_kit.header_registry import (
    to_canonical,
    match_kind,
    is_dynamic,
    is_variant_metafield,
)


def test_new_format_header_maps_to_canonical():
    assert to_canonical("URL handle") == "handle"
    assert to_canonical("Continue selling when out of stock") == "inventory_policy"


def test_legacy_alias_maps_to_canonical():
    assert to_canonical("Handle") == "handle"
    assert to_canonical("Variant SKU") == "sku"


def test_unknown_header_returns_none():
    assert to_canonical("Totally Unknown Column") is None


def test_match_kind_distinguishes_case_only_from_alias():
    # 新形式の大文字小文字違い = case_only（proven 修正対象）
    assert match_kind("url handle") == "case_only"
    # 旧形式 alias = alias（suggested）
    assert match_kind("Handle") == "alias"
    assert match_kind("URL handle") == "canonical"


def test_case_only_limited_to_primary_not_alias():
    # round-3 #2: alias の大小違い（"handle" 小文字 = legacy "Handle" の case 違い）は
    # case_only にしない。proven 改名で alias→canonical 改名されるのを防ぐため alias 扱い。
    assert match_kind("handle") == "alias"
    assert match_kind("variant sku") == "alias"  # legacy "Variant SKU" の case 違い
    # 一方 primary の case 違いは case_only（proven）
    assert match_kind("title") == "case_only"  # primary "Title" の case 違い


def test_current_official_columns_not_unknown():
    # round-3 #1: 現行公式列が unknown(F03d) に落ちないこと
    for col in [
        "Option1 LinkedTo",
        "Image position",
        "Product category",
        "Barcode",
        "Compare-at price",
        "Cost per item",
        "Variant image URL",
        "Gift card",
        "SEO title",
        "SEO description",
        "Collection",
    ]:
        assert match_kind(col) in ("canonical", "alias"), col
        assert match_kind(col) != "unknown", col


def test_product_metafield_is_dynamic_not_unknown():
    assert is_dynamic("Metafield: custom.spec [single_line_text_field]") is True
    assert match_kind("Metafield: custom.spec [single_line_text_field]") == "dynamic"


def test_market_price_columns_dynamic_with_variable_market_name():
    # round-4 #1: market 名は可変（International 固定でない）。dynamic 扱い。
    for col in [
        "Price / South America",
        "Compare-at price / South America",
        "Price / International",
        "Included / South America",
    ]:
        assert match_kind(col) == "dynamic", col


def test_bare_product_metafield_dynamic():
    # round-4 #1: bare product.metafields.<ns>.<key> 形式も dynamic
    assert match_kind("product.metafields.custom.spec") == "dynamic"


def test_bare_variant_metafield_is_variant_metafield():
    # round-4 #1: bare variant.metafields.<ns>.<key> は variant_metafield（dynamic でない）
    assert is_variant_metafield("variant.metafields.custom.x") is True
    assert match_kind("variant.metafields.custom.x") == "variant_metafield"


def test_variant_metafield_excluded_from_dynamic():
    assert is_dynamic("Variant Metafield: custom.x [number_integer]") is False
    assert is_variant_metafield("Variant Metafield: custom.x [number_integer]") is True
    assert (
        match_kind("Variant Metafield: custom.x [number_integer]")
        == "variant_metafield"
    )
