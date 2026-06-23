from __future__ import annotations
import re

from ..loader import LoadResult
from ..models import Finding, Severity, FixClass, ImportIntent, MAX_IMPORT_BYTES
from ..header_registry import match_kind, CANONICAL_TO_HEADERS

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SMART_QUOTES = ("‘", "’", "“", "”")
_MAX_BYTES = MAX_IMPORT_BYTES
_ROW_WARN_THRESHOLD = 5000
# F03c: ファイルに最低限必要な canonical 列（列そのものの存在を要求する。
# 値の空欄は R01/R02 が intent 別 severity で扱う。列の欠落は構造問題なので
# critical。spec F03c「Title/Handle 相当列が無い」に対応）。
_REQUIRED_CANONICAL = {"title", "handle"}


def _header_finding(rule_id, severity, fix_class, field_name, message, suggested_fix):
    return Finding(
        row=None,
        product_group_id=None,
        row_kind=None,
        handle=None,
        sku=None,
        severity=severity,
        rule_id=rule_id,
        field=field_name,
        message=message,
        suggested_fix=suggested_fix,
        fix_class=fix_class,
        auto_fixable=(fix_class == FixClass.PROVEN),
    )


def rule_f01c(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    out = []
    for row in load.rows:
        for col, val in row.cells.items():
            if _CONTROL_CHARS.search(val or ""):
                out.append(
                    Finding(
                        row=row.line_no,
                        product_group_id=row.product_group_id,
                        row_kind=row.row_kind,
                        handle=row.get("handle"),
                        sku=row.get("sku"),
                        severity=Severity.WARNING,
                        rule_id="F01c",
                        field=col,
                        message=f"Control character in column '{col}'.",
                        suggested_fix="Remove the control character manually.",
                        fix_class=FixClass.NONE,
                        auto_fixable=False,
                    )
                )
    return out


def rule_f02(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    out = []
    for row in load.rows:
        for col, val in row.cells.items():
            if any(q in (val or "") for q in _SMART_QUOTES):
                out.append(
                    Finding(
                        row=row.line_no,
                        product_group_id=row.product_group_id,
                        row_kind=row.row_kind,
                        handle=row.get("handle"),
                        sku=row.get("sku"),
                        severity=Severity.WARNING,
                        rule_id="F02",
                        field=col,
                        message=f"Smart/curly quotes in column '{col}'.",
                        suggested_fix="Review manually; not auto-replaced (body text vs CSV quoting cannot be distinguished).",
                        fix_class=FixClass.SUGGESTED,
                        auto_fixable=False,
                    )
                )
                break
    return out


def rule_f03a(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    out = []
    for col in load.header:
        if match_kind(col) == "case_only":
            out.append(
                _header_finding(
                    "F03a",
                    Severity.CRITICAL,
                    FixClass.PROVEN,
                    col,
                    f"Header '{col}' differs only by case from a known column.",
                    "Header case normalized automatically.",
                )
            )
    return out


def rule_f03b(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    out = []
    for col in load.header:
        if match_kind(col) == "alias":
            out.append(
                _header_finding(
                    "F03b",
                    Severity.WARNING,
                    FixClass.SUGGESTED,
                    col,
                    f"Header '{col}' is a legacy alias.",
                    "Consider renaming to the current header (not auto-applied; may change meaning).",
                )
            )
    return out


def rule_f03c(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    present = set(load.canonical_map.values())
    missing = _REQUIRED_CANONICAL - present
    out = []
    for key in sorted(missing):
        out.append(
            _header_finding(
                "F03c",
                Severity.CRITICAL,
                FixClass.NONE,
                key,
                f"Required column for '{key}' is missing.",
                f"Add the '{CANONICAL_TO_HEADERS[key][0]}' column.",
            )
        )
    return out


def rule_f03d(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    out = []
    for col in load.header:
        if match_kind(col) == "unknown":
            out.append(
                _header_finding(
                    "F03d",
                    Severity.WARNING,
                    FixClass.NONE,
                    col,
                    f"Unknown column '{col}' (possible typo).",
                    "Verify the column name; not removed or renamed automatically.",
                )
            )
    return out


def rule_f03e(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    out = []
    for col in load.header:
        if match_kind(col) == "variant_metafield":
            out.append(
                _header_finding(
                    "F03e",
                    Severity.WARNING,
                    FixClass.NONE,
                    col,
                    f"Variant metafield column '{col}' is not supported by standard product CSV import.",
                    "Remove or import variant metafields via a dedicated method.",
                )
            )
    return out


def rule_f04a(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    if load.raw_byte_size > _MAX_BYTES:
        return [
            _header_finding(
                "F04a",
                Severity.CRITICAL,
                FixClass.NONE,
                None,
                f"File is {load.raw_byte_size} bytes, over the 15MB Shopify import limit.",
                "Split the CSV into files under 15MB.",
            )
        ]
    return []


def rule_f04b(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    if len(load.rows) > _ROW_WARN_THRESHOLD:
        return [
            _header_finding(
                "F04b",
                Severity.WARNING,
                FixClass.NONE,
                None,
                f"File has {len(load.rows)} rows; consider splitting for reliability.",
                "Split into smaller files if import is slow or fails.",
            )
        ]
    return []


ALL_FILE_RULES = [
    rule_f01c,
    rule_f02,
    rule_f03a,
    rule_f03b,
    rule_f03c,
    rule_f03d,
    rule_f03e,
    rule_f04a,
    rule_f04b,
]
