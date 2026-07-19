import csv
from pathlib import Path
import pytest
from preflight_kit.loader import load_csv
from preflight_kit.engine import run_engine
from preflight_kit.fixer import apply_fixes
from preflight_kit.models import ImportIntent, Severity

FIX = Path(__file__).parent / "fixtures"


def _rule_ids(findings):
    return sorted({f.rule_id for f in findings})


def _severity_of(findings, rule_id):
    """指定 rule_id の Finding の severity 集合を返す（無ければ空集合）。"""
    return {f.severity for f in findings if f.rule_id == rule_id}


# (fixture dir, intent, expected rule_id subset that MUST appear,
#  rule_ids that MUST NOT appear)
CASES = [
    (
        "clean_new_format",
        "new",
        [],
        ["F03a", "F03b", "F03c", "F03d", "R01", "R02", "R03", "R05"],
    ),
    ("clean_legacy_alias", "new", ["F03b"], ["F03a", "F03d", "R01"]),
    ("multivariant_normal", "new", [], ["R03", "R01", "R02"]),
    ("image_rows_normal", "new", [], ["R03", "R01", "R02"]),
    ("case_only_header", "new", ["F03a"], ["F03b"]),
    ("unknown_metafield", "new", [], ["F03d"]),  # product metafield は警告しない
    ("variant_metafield", "new", ["F03e"], ["F03d"]),
    ("bom_utf8", "new", ["F01a"], ["F01b"]),
    ("non_utf8", "new", ["F01b"], ["F01a"]),
    ("option_dependency", "new", ["R05"], []),
    ("tracker_no_qty", "new", ["R08"], []),
    ("dup_product_start", "new", ["R03"], []),
    ("title_missing_new", "new", ["R01"], []),
    (
        "title_missing_mixed",
        "mixed",
        ["R01"],
        [],
    ),  # mixed でも R01 は出る（severity は別テストで検証）
    ("handle_missing_update", "update", ["R02"], []),
    ("variant_missing_handle", "new", ["R02"], []),  # variant 行 handle 欠落
    # 残りルールの per-rule golden（spec: 各ルールに最低1 fixture）
    ("control_char", "new", ["F01c"], []),
    ("smart_quotes", "new", ["F02"], []),
    ("missing_handle_column", "new", ["F03c"], []),
    ("over_15mb", "new", ["F04a"], []),
    ("dup_option_combo", "new", ["R04"], []),
    ("sku_reuse", "new", ["R06"], []),
    ("blank_sku", "new", ["R06"], []),
    ("invalid_inventory_policy", "new", ["R07"], []),
    ("missing_fulfillment", "new", ["R09"], []),
    ("bad_price", "new", ["R10"], []),
    ("alt_without_image", "new", ["R11"], []),
    ("local_image_path", "new", ["R12"], []),
    ("sku_scientific", "new", ["R13"], []),
    ("option2_without_option1", "new", ["R14"], []),
]


@pytest.mark.parametrize("case,intent,must,must_not", CASES)
def test_golden_rule_presence(case, intent, must, must_not):
    load = load_csv(str(FIX / case / "input.csv"))
    findings = run_engine(load, ImportIntent(intent))
    ids = _rule_ids(findings)
    for rid in must:
        assert rid in ids, f"{case}: expected {rid} in {ids}"
    for rid in must_not:
        assert rid not in ids, f"{case}: did NOT expect {rid} in {ids}"


# 必須欄マトリクス全セルの severity 回帰（#8/#9）。
# (fixture, rule_id, intent -> expected severity)。intent に無いキーは「その intent で
# その rule_id が出ない」ことを意味する。
SEVERITY_MATRIX = [
    # Title 欠落（product-start）: new/update=critical, mixed=warning
    (
        "title_missing_new",
        "R01",
        {
            "new": Severity.CRITICAL,
            "update": Severity.CRITICAL,
            "mixed": Severity.WARNING,
        },
    ),
    # handle 欠落（product-start）: update=critical, new/mixed=warning
    (
        "handle_missing_update",
        "R02",
        {
            "update": Severity.CRITICAL,
            "new": Severity.WARNING,
            "mixed": Severity.WARNING,
        },
    ),
    # handle 欠落（variant 行・親継承）: 全 intent で critical
    (
        "variant_missing_handle",
        "R02",
        {
            "new": Severity.CRITICAL,
            "update": Severity.CRITICAL,
            "mixed": Severity.CRITICAL,
        },
    ),
]


@pytest.mark.parametrize("case,rule_id,by_intent", SEVERITY_MATRIX)
def test_required_field_severity_matrix(case, rule_id, by_intent):
    load = load_csv(str(FIX / case / "input.csv"))
    for intent_name, expected_sev in by_intent.items():
        findings = run_engine(load, ImportIntent(intent_name))
        sevs = _severity_of(findings, rule_id)
        assert expected_sev in sevs, (
            f"{case}/{rule_id}/{intent_name}: expected {expected_sev}, got {sevs}"
        )
        # 反対 severity が混入しないこと（critical を期待する所に warning だけ等の取りこぼし防止）
        wrong = {Severity.CRITICAL, Severity.WARNING} - {expected_sev}
        for w in wrong:
            assert w not in sevs, (
                f"{case}/{rule_id}/{intent_name}: unexpected {w} in {sevs}"
            )


def test_bom_fixed_csv_has_no_bom():
    load = load_csv(str(FIX / "bom_utf8" / "input.csv"))
    findings = run_engine(load, ImportIntent.NEW)
    fix = apply_fixes(load, findings)
    assert not fix.header[0].startswith("﻿")
