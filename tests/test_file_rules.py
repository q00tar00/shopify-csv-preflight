from preflight_kit.loader import LoadResult
from preflight_kit.models import Row, Severity, FixClass, ImportIntent
from preflight_kit.rules.file_rules import (
    rule_f03a,
    rule_f03b,
    rule_f03c,
    rule_f03d,
    rule_f03e,
    rule_f04a,
)


def _load(header, rows=None, byte_size=100, canonical_map=None):
    return LoadResult(
        header=header,
        rows=rows or [],
        canonical_map=canonical_map or {},
        file_findings=[],
        encoding="utf-8",
        raw_byte_size=byte_size,
    )


def test_f03a_case_only_is_proven():
    load = _load(["url handle", "Title"])
    findings = rule_f03a(load, ImportIntent.MIXED)
    assert len(findings) == 1
    assert findings[0].rule_id == "F03a"
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].fix_class == FixClass.PROVEN


def test_f03b_alias_is_suggested():
    load = _load(["Handle", "Title"])
    findings = rule_f03b(load, ImportIntent.MIXED)
    assert any(
        f.rule_id == "F03b" and f.fix_class == FixClass.SUGGESTED for f in findings
    )


def test_f03c_missing_handle_column_is_critical():
    # handle 列が完全に無い = 構造問題で critical（#4）
    load = _load(["Title"], canonical_map={"Title": "title"})
    findings = rule_f03c(load, ImportIntent.MIXED)
    assert any(
        f.rule_id == "F03c" and f.field == "handle" and f.severity == Severity.CRITICAL
        for f in findings
    )


def test_f03c_present_title_and_handle_no_finding():
    load = _load(
        ["Title", "URL handle"],
        canonical_map={"Title": "title", "URL handle": "handle"},
    )
    assert rule_f03c(load, ImportIntent.MIXED) == []


def test_f03d_unknown_is_warning_none():
    load = _load(["Title", "Totally Unknown Column"])
    findings = rule_f03d(load, ImportIntent.MIXED)
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARNING
    assert findings[0].fix_class == FixClass.NONE


def test_f03d_does_not_flag_product_metafield():
    load = _load(["Title", "Metafield: custom.spec [single_line_text_field]"])
    assert rule_f03d(load, ImportIntent.MIXED) == []


def test_f03e_variant_metafield_warned():
    load = _load(["Title", "Variant Metafield: custom.x [number_integer]"])
    findings = rule_f03e(load, ImportIntent.MIXED)
    assert any(f.rule_id == "F03e" and f.severity == Severity.WARNING for f in findings)


def test_f04a_over_15mb_is_critical():
    load = _load(["Title"], byte_size=15 * 1024 * 1024 + 1)
    findings = rule_f04a(load, ImportIntent.MIXED)
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].rule_id == "F04a"


def _row(line, cells):
    from preflight_kit.models import RowKind

    return Row(
        line_no=line,
        cells=dict(cells),
        canonical=dict(cells),
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )


def test_f01c_control_char_warning():
    from preflight_kit.rules.file_rules import rule_f01c

    load = _load(["Title"], rows=[_row(1, {"Title": "Te\x07e"})])
    findings = rule_f01c(load, ImportIntent.MIXED)
    assert any(f.rule_id == "F01c" and f.severity == Severity.WARNING for f in findings)


def test_f02_smart_quotes_suggested():
    from preflight_kit.rules.file_rules import rule_f02

    load = _load(["Title"], rows=[_row(1, {"Title": "“curly”"})])
    findings = rule_f02(load, ImportIntent.MIXED)
    assert any(
        f.rule_id == "F02" and f.fix_class == FixClass.SUGGESTED for f in findings
    )


def test_f04b_many_rows_warning():
    from preflight_kit.rules.file_rules import rule_f04b

    rows = [_row(i, {"Title": "x"}) for i in range(5001)]
    load = _load(["Title"], rows=rows)
    findings = rule_f04b(load, ImportIntent.MIXED)
    assert any(f.rule_id == "F04b" and f.severity == Severity.WARNING for f in findings)
