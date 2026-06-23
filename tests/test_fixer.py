from csv_preflight.loader import LoadResult
from csv_preflight.models import Row, RowKind, Severity, FixClass, Finding, ImportIntent
from csv_preflight.fixer import apply_fixes, FixResult


def _f03a(col):
    return Finding(
        row=None,
        product_group_id=None,
        row_kind=None,
        handle=None,
        sku=None,
        severity=Severity.CRITICAL,
        rule_id="F03a",
        field=col,
        message="m",
        suggested_fix="s",
        fix_class=FixClass.PROVEN,
        auto_fixable=True,
    )


def _load(header, rows):
    return LoadResult(
        header=header,
        rows=rows,
        canonical_map={},
        file_findings=[],
        encoding="utf-8",
        raw_byte_size=10,
    )


def test_f03a_header_case_normalized():
    row = Row(
        line_no=1,
        cells={"url handle": "tee", "Title": "Tee"},
        canonical={},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    load = _load(["url handle", "Title"], [row])
    result = apply_fixes(load, [_f03a("url handle")])
    assert isinstance(result, FixResult)
    assert result.header == ["URL handle", "Title"]  # canonical 正式名へ正規化
    assert result.rows == [["tee", "Tee"]]  # 列順・値は保持
    assert len(result.applied) == 1


def test_suggested_not_applied():
    row = Row(
        line_no=1,
        cells={"Handle": "tee"},
        canonical={},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    load = _load(["Handle"], [row])
    f03b = Finding(
        row=None,
        product_group_id=None,
        row_kind=None,
        handle=None,
        sku=None,
        severity=Severity.WARNING,
        rule_id="F03b",
        field="Handle",
        message="m",
        suggested_fix="s",
        fix_class=FixClass.SUGGESTED,
        auto_fixable=False,
    )
    result = apply_fixes(load, [f03b])
    assert result.header == ["Handle"]  # alias は改名しない
    assert result.applied == []


def test_unknown_column_preserved():
    row = Row(
        line_no=1,
        cells={"Title": "Tee", "Weird": "x"},
        canonical={},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    load = _load(["Title", "Weird"], [row])
    result = apply_fixes(load, [])
    assert result.header == ["Title", "Weird"]
    assert result.rows == [["Tee", "x"]]


def test_f01a_bom_counted_as_applied():
    # F01a（BOM）は loader が除去済みでも applied/auto_fixed として記録する（#5）
    row = Row(
        line_no=1,
        cells={"Title": "Tee"},
        canonical={},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    f01a = Finding(
        row=None,
        product_group_id=None,
        row_kind=None,
        handle=None,
        sku=None,
        severity=Severity.CRITICAL,
        rule_id="F01a",
        field=None,
        message="m",
        suggested_fix="s",
        fix_class=FixClass.PROVEN,
        auto_fixable=True,
    )
    result = apply_fixes(_load(["Title"], [row]), [f01a])
    assert any(f.rule_id == "F01a" and f.auto_fixed for f in result.applied)


def test_proven_but_not_auto_fixable_is_not_applied():
    # fix_class=proven でも auto_fixable=False なら適用しない（#6）
    row = Row(
        line_no=1,
        cells={"url handle": "tee"},
        canonical={},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    f = Finding(
        row=None,
        product_group_id=None,
        row_kind=None,
        handle=None,
        sku=None,
        severity=Severity.CRITICAL,
        rule_id="F03a",
        field="url handle",
        message="m",
        suggested_fix="s",
        fix_class=FixClass.PROVEN,
        auto_fixable=False,
    )
    result = apply_fixes(_load(["url handle"], [row]), [f])
    assert result.header == ["url handle"]  # 改名されない
    assert result.applied == []
