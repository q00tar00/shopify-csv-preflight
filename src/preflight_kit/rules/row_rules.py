from __future__ import annotations
import re
from collections import defaultdict

from ..loader import LoadResult
from ..models import Finding, RowKind, Severity, FixClass, ImportIntent

_DANGEROUS_SKU = re.compile(r"[,\"\n\r\t]")
_SCI_NOTATION = re.compile(r"^\d+(\.\d+)?[eE][+-]?\d+$")
_INVENTORY_POLICY_VALID = {"deny", "continue"}


def _row_finding(
    row, rule_id, severity, message, suggested_fix, field_name, fix_class=FixClass.NONE
):
    return Finding(
        row=row.line_no,
        product_group_id=row.product_group_id,
        row_kind=row.row_kind,
        handle=row.get("handle"),
        sku=row.get("sku"),
        severity=severity,
        rule_id=rule_id,
        field=field_name,
        message=message,
        suggested_fix=suggested_fix,
        fix_class=fix_class,
        auto_fixable=(fix_class == FixClass.PROVEN),
    )


def _blank(v: str | None) -> bool:
    return (v or "").strip() == ""


def rule_r01(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """product-start 行の Title 欠落。new/update=critical, mixed=warning。"""
    out = []
    for row in load.rows:
        if not row.is_product_start:
            continue
        if _blank(row.get("title")):
            sev = (
                Severity.WARNING if intent == ImportIntent.MIXED else Severity.CRITICAL
            )
            out.append(
                _row_finding(
                    row,
                    "R01",
                    sev,
                    "Product-start row is missing Title.",
                    "Add a Title for the product.",
                    "Title",
                )
            )
    return out


def rule_r02(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """handle 欠落。
    - product-start 行: update=critical, new/mixed=warning（必須欄マトリクス）。
    - variant/image 行: 親グループ handle の継承が全 intent で必須。空なら critical
      （#3: マトリクスの variant/image セル。ファイル単体で親を特定できない）。
    """
    out = []
    for row in load.rows:
        if not _blank(row.get("handle")):
            continue
        if row.is_product_start:
            sev = (
                Severity.CRITICAL if intent == ImportIntent.UPDATE else Severity.WARNING
            )
            out.append(
                _row_finding(
                    row,
                    "R02",
                    sev,
                    "Product-start row is missing URL handle.",
                    "Add a URL handle (required to target an existing product on update).",
                    "URL handle",
                )
            )
        else:
            # variant / image 行は親 handle の継承が必須（全 intent で critical）
            out.append(
                _row_finding(
                    row,
                    "R02",
                    Severity.CRITICAL,
                    "Variant/image row is missing the parent URL handle.",
                    "Repeat the parent product's URL handle on every variant/image row.",
                    "URL handle",
                )
            )
    return out


def rule_r03(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """同一 handle に複数 product-start 行（サイレント上書き事故）。"""
    by_handle: dict[str, list] = defaultdict(list)
    for row in load.rows:
        if row.is_product_start and not _blank(row.get("handle")):
            by_handle[row.get("handle").strip()].append(row)
    out = []
    for handle, rows in by_handle.items():
        if len(rows) > 1:
            line_nos = ", ".join(str(r.line_no) for r in rows)
            for r in rows:
                out.append(
                    _row_finding(
                        r,
                        "R03",
                        Severity.CRITICAL,
                        f"{len(rows)} product-start rows share handle '{handle}' (rows {line_nos}).",
                        "Keep one product-start row per handle; merge or rename duplicates.",
                        "URL handle",
                    )
                )
    return out


def rule_r04(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """グループ内 Option 値の組み合わせ重複。"""
    seen: dict[str, dict] = defaultdict(dict)
    out = []
    for row in load.rows:
        gid = row.product_group_id
        if gid is None:
            continue
        combo = (
            (row.get("option1_value") or "").strip(),
            (row.get("option2_value") or "").strip(),
            (row.get("option3_value") or "").strip(),
        )
        if any(combo):
            if combo in seen[gid]:
                out.append(
                    _row_finding(
                        row,
                        "R04",
                        Severity.CRITICAL,
                        f"Duplicate option combination {combo} within product group.",
                        "Remove or fix the duplicate variant.",
                        "Option1 value",
                    )
                )
            else:
                seen[gid][combo] = row.line_no
    return out


def rule_r05(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """Option1 dependency 違反。"""
    out = []
    for row in load.rows:
        o1n, o1v = row.get("option1_name"), row.get("option1_value")
        o2n, o2v = row.get("option2_name"), row.get("option2_value")
        problem = None
        if not _blank(o1n) and _blank(o1v):
            problem = "Option1 name set but Option1 value is empty."
        elif _blank(o1n) and not _blank(o1v):
            problem = "Option1 value set but Option1 name is empty."
        elif (not _blank(o2n) or not _blank(o2v)) and _blank(o1n):
            problem = "Option2 present but Option1 is missing."
        if problem:
            out.append(
                _row_finding(
                    row,
                    "R05",
                    Severity.CRITICAL,
                    problem,
                    "Fix option name/value pairing (Shopify 'Line is invalid').",
                    "Option1 name",
                )
            )
    return out


def rule_r06(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """SKU 空欄 / グループ跨ぎ重複 / 危険文字。"""
    out = []
    # SKU 列が CSV に存在するか（列ごと無いのは構造問題で R06 の対象外）。
    sku_present = "sku" in set(load.canonical_map.values())
    sku_groups: dict[str, set] = defaultdict(set)
    for row in load.rows:
        sku = (row.get("sku") or "").strip()
        if sku:
            sku_groups[sku].add(row.product_group_id)
            if _DANGEROUS_SKU.search(sku):
                out.append(
                    _row_finding(
                        row,
                        "R06",
                        Severity.WARNING,
                        f"SKU '{sku}' contains characters that may break CSV (comma/quote/newline/tab).",
                        "Review and clean the SKU.",
                        "SKU",
                    )
                )
        elif sku_present and row.row_kind != RowKind.IMAGE:
            # SKU 列はあるが値が空（image 行は SKU 不要なので除外）。
            out.append(
                _row_finding(
                    row,
                    "R06",
                    Severity.WARNING,
                    "SKU is empty (inventory/variant tracking may not work).",
                    "Set a unique SKU for this variant, or confirm it is intentionally blank.",
                    "SKU",
                )
            )
    for row in load.rows:
        sku = (row.get("sku") or "").strip()
        if sku and len(sku_groups[sku]) > 1:
            out.append(
                _row_finding(
                    row,
                    "R06",
                    Severity.WARNING,
                    f"SKU '{sku}' is reused across multiple product groups.",
                    "Ensure SKUs are unique per variant.",
                    "SKU",
                )
            )
    return out


def rule_r07(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """inventory_policy が許容値以外。SoT 未確定のため warning + suggested 止まり。"""
    out = []
    for row in load.rows:
        val = (row.get("inventory_policy") or "").strip()
        if val and val.lower() not in _INVENTORY_POLICY_VALID:
            out.append(
                _row_finding(
                    row,
                    "R07",
                    Severity.WARNING,
                    f"inventory_policy '{val}' is not a documented value (deny/continue).",
                    "Verify against current Shopify CSV docs; not auto-normalized (SoT unsettled).",
                    "Continue selling when out of stock",
                    fix_class=FixClass.SUGGESTED,
                )
            )
    return out


def rule_r08(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """inventory_tracker ありで qty が非数値/空。"""
    out = []
    for row in load.rows:
        tracker = (row.get("inventory_tracker") or "").strip()
        if not tracker:
            continue
        qty = (row.get("inventory_qty") or "").strip()
        if qty == "" or not re.fullmatch(r"-?\d+", qty):
            out.append(
                _row_finding(
                    row,
                    "R08",
                    Severity.WARNING,
                    f"Inventory tracker '{tracker}' set but inventory quantity is empty/non-numeric.",
                    "Set a numeric inventory quantity when a tracker is active.",
                    "Inventory quantity",
                )
            )
    return out


def rule_r09(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """fulfillment_service 空欄（情報提供）。"""
    out = []
    for row in load.rows:
        if row.row_kind == RowKind.IMAGE:
            continue
        if (row.get("sku") or "").strip() and _blank(row.get("fulfillment_service")):
            out.append(
                _row_finding(
                    row,
                    "R09",
                    Severity.WARNING,
                    "Fulfillment service is empty (defaults to manual).",
                    "Set explicitly if a non-manual fulfillment service is required.",
                    "Fulfillment service",
                )
            )
    return out


def rule_r10(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """価格が非数値 / 負数 / Compare-at <= Price。"""
    out = []
    for row in load.rows:
        price_s = (row.get("price") or "").strip()
        price: float | None = None
        if price_s:
            try:
                price = float(price_s)
            except ValueError:
                price = None
                out.append(
                    _row_finding(
                        row,
                        "R10",
                        Severity.WARNING,
                        f"Price '{price_s}' is not numeric.",
                        "Use a numeric price.",
                        "Price",
                    )
                )
            if price is not None and price < 0:
                out.append(
                    _row_finding(
                        row,
                        "R10",
                        Severity.WARNING,
                        f"Price '{price_s}' is negative.",
                        "Use a non-negative price.",
                        "Price",
                    )
                )
        # compare_at_price は price とは独立に数値判定する。ここを price の
        # try に同居させると compare_at の非数値が「Price is not numeric」と
        # 誤報告される（round-1 non-blocking）。
        cap_s = (row.get("compare_at_price") or "").strip()
        if cap_s:
            try:
                cap = float(cap_s)
            except ValueError:
                out.append(
                    _row_finding(
                        row,
                        "R10",
                        Severity.WARNING,
                        f"Compare-at price '{cap_s}' is not numeric.",
                        "Use a numeric compare-at price.",
                        "Compare-at price",
                    )
                )
            else:
                if price is not None and cap <= price:
                    out.append(
                        _row_finding(
                            row,
                            "R10",
                            Severity.WARNING,
                            f"Compare-at price {cap} <= price {price}.",
                            "Compare-at price should exceed price to show a discount.",
                            "Compare-at price",
                        )
                    )
    return out


def rule_r11(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """image alt 有 but image_src 空。"""
    out = []
    for row in load.rows:
        if not _blank(row.get("image_alt")) and _blank(row.get("image_src")):
            out.append(
                _row_finding(
                    row,
                    "R11",
                    Severity.CRITICAL,
                    "Image alt text present but image URL is empty.",
                    "Add the image URL or remove the alt text.",
                    "Image alt text",
                )
            )
    return out


def rule_r12(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """image_src の URL 構文不正 / scheme 無 / ローカルパス。"""
    out = []
    for row in load.rows:
        src = (row.get("image_src") or "").strip()
        if src and not re.match(r"^https?://", src, re.IGNORECASE):
            out.append(
                _row_finding(
                    row,
                    "R12",
                    Severity.WARNING,
                    f"Image URL '{src}' has no http(s) scheme (local path or malformed).",
                    "Use a public http(s) URL. (HTTP reachability is not checked.)",
                    "Product image URL",
                )
            )
    return out


def rule_r13(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """Excel 由来の SKU 科学表記。"""
    out = []
    for row in load.rows:
        sku = (row.get("sku") or "").strip()
        if sku and _SCI_NOTATION.match(sku):
            out.append(
                _row_finding(
                    row,
                    "R13",
                    Severity.WARNING,
                    f"SKU '{sku}' looks like Excel scientific notation.",
                    "Re-format the SKU as text to avoid data loss.",
                    "SKU",
                )
            )
    return out


def rule_r14(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    """option 位置入れ替えの疑い（ファイル単体で確定不能・注意喚起のみ）。"""
    out = []
    for row in load.rows:
        if (
            row.is_product_start
            and _blank(row.get("option1_name"))
            and not _blank(row.get("option2_name"))
        ):
            out.append(
                _row_finding(
                    row,
                    "R14",
                    Severity.WARNING,
                    "Option2 set without Option1 on product-start row (possible option position shift).",
                    "Verify option positions against the existing product (not checkable from file alone).",
                    "Option1 name",
                )
            )
    return out


ALL_ROW_RULES = [
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
]
