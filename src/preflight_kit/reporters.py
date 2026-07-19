from __future__ import annotations
import csv

from .models import Finding, Severity, FixClass

_ERROR_COLUMNS = [
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
]

_UNCHECKED_EN = (
    "Not checked by this tool: image URL public reachability, handle "
    "overwrite/ignore against an existing store, metafield product reference "
    "resolution, and option position consistency with existing products."
)
_UNCHECKED_JA = (
    "本CLIが未検査の範囲: 画像URLの公開到達性、既存ストアとの handle "
    "overwrite/ignore、metafield product reference の解決、既存商品との option 位置整合。"
)
_NO_BLOCKING = "No blocking findings detected within implemented checks"


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (Severity, FixClass)):
        return v.value
    if hasattr(v, "value"):
        return v.value
    return str(v)


def write_errors_csv(findings: list[Finding], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_ERROR_COLUMNS)
        for f in findings:
            writer.writerow(
                [
                    _cell(f.row),
                    _cell(f.product_group_id),
                    _cell(f.row_kind),
                    _cell(f.handle),
                    _cell(f.sku),
                    _cell(f.severity),
                    _cell(f.rule_id),
                    _cell(f.field),
                    _cell(f.message),
                    _cell(f.suggested_fix),
                    _cell(f.fix_class),
                    _cell(f.auto_fixed),
                ]
            )


def render_report_md(
    findings: list[Finding],
    *,
    lang: str,
    scanned_rows: int,
    group_count: int,
    applied: list[Finding],
) -> str:
    crit = [f for f in findings if f.severity == Severity.CRITICAL]
    warn = [f for f in findings if f.severity == Severity.WARNING]
    suggested = [f for f in findings if f.fix_class == FixClass.SUGGESTED]
    lines: list[str] = []

    if lang == "ja":
        lines.append("# Shopify CSV Preflight Report")
        lines.append("")
        lines.append(
            f"- 概要: 検査行数 {scanned_rows} / 商品グループ数 {group_count} / "
            f"critical {len(crit)}件 / warning {len(warn)}件 / "
            f"自動修正(proven) {len(applied)}件 / 提案(suggested) {len(suggested)}件"
        )
        crit_head, warn_head = (
            "## Critical（インポート前に必ず直す）",
            "## Warning（確認推奨）",
        )
        applied_head, sug_head = (
            "## 自動修正した内容（proven）",
            "## 提案（suggested・CSV未反映）",
        )
        unchecked_head, next_head = "## 未検査範囲", "## 次のアクション"
        unchecked = _UNCHECKED_JA
        verdict = (
            (_NO_BLOCKING + "（import可能を保証しない範囲あり）")
            if not crit
            else "Critical があります。import 前に解消してください。import可能を保証しません。"
        )
    else:
        lines.append("# Shopify CSV Preflight Report")
        lines.append("")
        lines.append(
            f"- Summary: scanned rows {scanned_rows} / product groups {group_count} / "
            f"{len(crit)} critical / {len(warn)} warning / "
            f"{len(applied)} auto-fixed (proven) / {len(suggested)} suggested"
        )
        crit_head, warn_head = (
            "## Critical (fix before import)",
            "## Warning (review recommended)",
        )
        applied_head, sug_head = (
            "## Auto-fixed (proven)",
            "## Suggested (not applied to CSV)",
        )
        unchecked_head, next_head = "## Not checked", "## Next actions"
        unchecked = _UNCHECKED_EN
        verdict = (
            (_NO_BLOCKING + " (import not guaranteed).")
            if not crit
            else "Critical findings present. Resolve before import. Import is not guaranteed."
        )

    def _section(head, items):
        lines.append("")
        lines.append(head)
        if not items:
            lines.append("- (none)")
        for f in items:
            loc = f"row {f.row}" if f.row else "file"
            lines.append(f"- [{f.rule_id}] {loc}: {f.message}")

    _section(crit_head, crit)
    _section(warn_head, warn)
    _section(applied_head, applied)
    _section(sug_head, suggested)
    lines.append("")
    lines.append(unchecked_head)
    lines.append(f"- {unchecked}")
    lines.append("")
    lines.append(next_head)
    lines.append(f"- {verdict}")
    return "\n".join(lines) + "\n"
