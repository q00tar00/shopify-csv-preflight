from csv_preflight.loader import LoadResult
from csv_preflight.models import Row, RowKind, Severity, FixClass, ImportIntent
from csv_preflight.rules.row_rules import (
    rule_r01,
    rule_r02,
    rule_r03,
    rule_r04,
    rule_r05,
    rule_r06,
    rule_r07,
    rule_r08,
    rule_r09,
    rule_r10,
    rule_r11,
    rule_r12,
    rule_r13,
    rule_r14,
)


def _row(line, canonical, kind=RowKind.PRODUCT, start=True, gid="g1"):
    return Row(
        line_no=line,
        cells=dict(canonical),
        canonical=dict(canonical),
        product_group_id=gid,
        row_kind=kind,
        is_product_start=start,
    )


def _load(rows, canonical_map=None):
    return LoadResult(
        header=[],
        rows=rows,
        canonical_map=canonical_map or {},
        file_findings=[],
        encoding="utf-8",
        raw_byte_size=10,
    )


def test_r01_title_missing_critical_when_new():
    load = _load([_row(1, {"handle": "tee"})])  # title 欠落
    findings = rule_r01(load, ImportIntent.NEW)
    assert findings[0].severity == Severity.CRITICAL


def test_r01_title_missing_warning_when_mixed():
    load = _load([_row(1, {"handle": "tee"})])
    findings = rule_r01(load, ImportIntent.MIXED)
    assert findings[0].severity == Severity.WARNING


def test_r01_variant_row_title_blank_is_ok():
    rows = [
        _row(1, {"handle": "tee", "title": "Tee"}, start=True),
        _row(2, {"handle": "tee"}, kind=RowKind.VARIANT, start=False),
    ]
    findings = rule_r01(_load(rows), ImportIntent.NEW)
    assert findings == []


def test_r02_handle_missing_critical_when_update():
    load = _load([_row(1, {"title": "Tee"})])  # handle 欠落
    findings = rule_r02(load, ImportIntent.UPDATE)
    assert findings[0].severity == Severity.CRITICAL


def test_r02_handle_missing_warning_when_new():
    load = _load([_row(1, {"title": "Tee"})])
    findings = rule_r02(load, ImportIntent.NEW)
    assert findings[0].severity == Severity.WARNING


def test_r03_multiple_product_start_same_handle_critical():
    rows = [
        _row(1, {"handle": "tee", "title": "Tee"}, start=True, gid="g1"),
        _row(2, {"handle": "tee", "title": "Tee Again"}, start=True, gid="g2"),
    ]
    findings = rule_r03(_load(rows), ImportIntent.MIXED)
    assert any(f.rule_id == "R03" and f.severity == Severity.CRITICAL for f in findings)


def test_r03_normal_multivariant_not_flagged():
    rows = [
        _row(1, {"handle": "tee", "title": "Tee"}, start=True, gid="g1"),
        _row(2, {"handle": "tee"}, kind=RowKind.VARIANT, start=False, gid="g1"),
    ]
    assert rule_r03(_load(rows), ImportIntent.MIXED) == []


def test_r05_option_value_without_name():
    load = _load(
        [_row(1, {"handle": "tee", "title": "Tee", "option1_value": "Red"})]
    )  # option1_name 空
    findings = rule_r05(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R05" and f.severity == Severity.CRITICAL for f in findings)


def test_r08_tracker_set_but_qty_empty():
    load = _load(
        [
            _row(
                1,
                {
                    "handle": "tee",
                    "title": "Tee",
                    "inventory_tracker": "shopify",
                    "inventory_qty": "",
                },
            )
        ]
    )
    findings = rule_r08(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R08" and f.severity == Severity.WARNING for f in findings)


def test_r02_variant_row_missing_handle_critical_all_intents():
    # variant 行で親 handle 欠落 = 全 intent で critical（#3）
    rows = [
        _row(1, {"handle": "tee", "title": "Tee"}, start=True),
        _row(2, {"title": ""}, kind=RowKind.VARIANT, start=False),
    ]
    for intent in (ImportIntent.NEW, ImportIntent.UPDATE, ImportIntent.MIXED):
        findings = rule_r02(_load(rows), intent)
        assert any(
            f.rule_id == "R02" and f.row == 2 and f.severity == Severity.CRITICAL
            for f in findings
        ), intent


def test_r04_duplicate_option_combo():
    rows = [
        _row(1, {"handle": "tee", "title": "Tee", "option1_value": "Red"}, gid="g1"),
        _row(
            2,
            {"handle": "tee", "option1_value": "Red"},
            kind=RowKind.VARIANT,
            start=False,
            gid="g1",
        ),
    ]
    findings = rule_r04(_load(rows), ImportIntent.MIXED)
    assert any(f.rule_id == "R04" and f.severity == Severity.CRITICAL for f in findings)


def test_r06_sku_reused_across_groups_warning():
    rows = [
        _row(1, {"handle": "a", "title": "A", "sku": "DUP"}, gid="g1"),
        _row(2, {"handle": "b", "title": "B", "sku": "DUP"}, gid="g2"),
    ]
    findings = rule_r06(_load(rows), ImportIntent.MIXED)
    assert any(f.rule_id == "R06" for f in findings)


def test_r06_blank_sku_warning_when_column_present():
    # round-5 #2: SKU 列があり値が空 = R06 warning（image 行は除外）
    rows = [_row(1, {"handle": "tee", "title": "Tee", "sku": ""})]
    findings = rule_r06(_load(rows, canonical_map={"SKU": "sku"}), ImportIntent.MIXED)
    assert any(f.rule_id == "R06" and "empty" in f.message.lower() for f in findings)


def test_r06_blank_sku_not_flagged_on_image_row():
    rows = [
        _row(
            1,
            {"handle": "tee", "title": "Tee", "sku": ""},
            kind=RowKind.IMAGE,
            start=False,
        )
    ]
    findings = rule_r06(_load(rows, canonical_map={"SKU": "sku"}), ImportIntent.MIXED)
    assert not any(f.rule_id == "R06" for f in findings)


def test_r06_no_blank_warning_when_sku_column_absent():
    # SKU 列そのものが無いファイルでは空欄警告を出さない（列欠落は構造問題で対象外）
    rows = [_row(1, {"handle": "tee", "title": "Tee"})]
    findings = rule_r06(
        _load(rows, canonical_map={"Title": "title"}), ImportIntent.MIXED
    )
    assert not any(f.rule_id == "R06" for f in findings)


def test_r07_invalid_inventory_policy_suggested():
    load = _load(
        [_row(1, {"handle": "tee", "title": "Tee", "inventory_policy": "false"})]
    )
    findings = rule_r07(load, ImportIntent.MIXED)
    assert any(
        f.rule_id == "R07"
        and f.fix_class == FixClass.SUGGESTED
        and f.severity == Severity.WARNING
        for f in findings
    )


def test_r09_fulfillment_service_empty_warning():
    load = _load(
        [
            _row(
                1,
                {
                    "handle": "tee",
                    "title": "Tee",
                    "sku": "S1",
                    "fulfillment_service": "",
                },
            )
        ]
    )
    findings = rule_r09(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R09" for f in findings)


def test_r10_compare_at_not_greater_than_price():
    load = _load(
        [
            _row(
                1,
                {
                    "handle": "tee",
                    "title": "Tee",
                    "price": "1000",
                    "compare_at_price": "1000",
                },
            )
        ]
    )
    findings = rule_r10(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R10" for f in findings)


def test_r10_non_numeric_price():
    load = _load([_row(1, {"handle": "tee", "title": "Tee", "price": "abc"})])
    findings = rule_r10(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R10" for f in findings)


def test_r10_non_numeric_compare_at_reports_compare_at_field():
    # round-1 non-blocking #4 回帰: compare_at が非数値 + price 数値のとき、
    # 「Price is not numeric」と誤報告せず compare_at 列を正しく指す。
    load = _load(
        [
            _row(
                1,
                {
                    "handle": "tee",
                    "title": "Tee",
                    "price": "1000",
                    "compare_at_price": "abc",
                },
            )
        ]
    )
    findings = rule_r10(load, ImportIntent.MIXED)
    r10 = [f for f in findings if f.rule_id == "R10"]
    assert len(r10) == 1
    # Price ではなく Compare-at price を指す
    assert r10[0].field == "Compare-at price"
    assert "Price '1000' is not numeric" not in r10[0].message


def test_r11_alt_without_image_src_critical():
    load = _load(
        [
            _row(
                1,
                {"handle": "tee", "title": "Tee", "image_alt": "alt", "image_src": ""},
            )
        ]
    )
    findings = rule_r11(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R11" and f.severity == Severity.CRITICAL for f in findings)


def test_r12_image_src_without_scheme_warning():
    load = _load(
        [_row(1, {"handle": "tee", "title": "Tee", "image_src": "/local/path.jpg"})]
    )
    findings = rule_r12(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R12" for f in findings)


def test_r13_sku_scientific_notation_warning():
    load = _load([_row(1, {"handle": "tee", "title": "Tee", "sku": "1.23E+11"})])
    findings = rule_r13(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R13" for f in findings)


def test_r14_option2_without_option1_warning():
    load = _load(
        [_row(1, {"handle": "tee", "title": "Tee", "option2_name": "Size"})]
    )  # option1_name 空
    findings = rule_r14(load, ImportIntent.MIXED)
    assert any(f.rule_id == "R14" for f in findings)
