from preflight_kit.models import (
    Severity,
    FixClass,
    RowKind,
    ImportIntent,
    Row,
    Finding,
)


def test_row_get_returns_canonical_value():
    row = Row(line_no=1, cells={"Title": "Tee"}, canonical={"title": "Tee"})
    assert row.get("title") == "Tee"
    assert row.get("missing") is None


def test_finding_defaults_auto_fixed_false():
    f = Finding(
        row=1,
        product_group_id=None,
        row_kind=RowKind.PRODUCT,
        handle="tee",
        sku=None,
        severity=Severity.CRITICAL,
        rule_id="R01",
        field="Title",
        message="m",
        suggested_fix="s",
        fix_class=FixClass.NONE,
        auto_fixable=False,
    )
    assert f.auto_fixed is False
    assert Severity.CRITICAL.value == "critical"
    assert ImportIntent.MIXED.value == "mixed"
