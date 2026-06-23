import csv
from pathlib import Path
from csv_preflight.models import Finding, Severity, FixClass, RowKind
from csv_preflight.reporters import write_errors_csv, render_report_md


def _f(rule_id, severity, fix_class=FixClass.NONE):
    return Finding(
        row=42,
        product_group_id="g7",
        row_kind=RowKind.PRODUCT,
        handle="tee",
        sku="TEE-1",
        severity=severity,
        rule_id=rule_id,
        field="Title",
        message="msg",
        suggested_fix="fix",
        fix_class=fix_class,
        auto_fixable=False,
    )


def test_errors_csv_has_all_columns(tmp_path):
    path = tmp_path / "errors.csv"
    write_errors_csv([_f("R01", Severity.CRITICAL)], str(path))
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["row"] == "42"
    assert rows[0]["rule_id"] == "R01"
    assert rows[0]["severity"] == "critical"
    assert set(rows[0].keys()) == {
        "row",
        "product_group_id",
        "row_kind",
        "handle",
        "sku",
        "severity",
        "rule_id",
        "field",
        "message",
        "suggested_fix",
        "fix_class",
        "auto_fixed",
    }


def test_report_no_blocking_phrase_when_zero_critical_en():
    md = render_report_md(
        [_f("R06", Severity.WARNING)],
        lang="en",
        scanned_rows=5,
        group_count=2,
        applied=[],
    )
    assert "No blocking findings detected within implemented checks" in md
    # 未検査範囲を必ず併記
    assert "not checked" in md.lower()


def test_report_lists_critical_section_ja():
    md = render_report_md(
        [_f("R01", Severity.CRITICAL)],
        lang="ja",
        scanned_rows=5,
        group_count=2,
        applied=[],
    )
    assert "Critical" in md
    assert "R01" in md
    # import 可能と断定しない
    assert "import可能を保証" in md or "保証しない" in md
