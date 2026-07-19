from __future__ import annotations
from dataclasses import dataclass

from .loader import LoadResult
from .models import Finding, FixClass
from .header_registry import to_canonical, CANONICAL_TO_HEADERS


@dataclass
class FixResult:
    header: list[str]
    rows: list[list[str]]
    applied: list[Finding]


def _is_proven(f: Finding) -> bool:
    # spec: fix_class==proven かつ auto_fixable==True の両方を要求（#6）。
    return f.fix_class == FixClass.PROVEN and f.auto_fixable


def apply_fixes(load: LoadResult, findings: list[Finding]) -> FixResult:
    applied: list[Finding] = []

    # F01a（BOM 除去）は loader が既にバイト列から除去済み。fixer は適用済みとして
    # applied に取り込み auto_fixed=True にする（#5: report に proven 適用を出す）。
    applied.extend(f for f in findings if f.rule_id == "F01a" and _is_proven(f))

    # F03a: header case-only 修正（proven）。元列名 -> canonical 正式名へ。
    f03a_cols = {f.field for f in findings if f.rule_id == "F03a" and _is_proven(f)}
    new_header: list[str] = []
    for col in load.header:
        if col in f03a_cols:
            key = to_canonical(col)
            primary = CANONICAL_TO_HEADERS[key][0] if key else col
            new_header.append(primary)
        else:
            new_header.append(col)
    applied.extend(f for f in findings if f.rule_id == "F03a" and _is_proven(f))

    # 行は列順を保持して元の値をそのまま出す（行順保持）。
    # F04c の余剰セル（extra_cells）は silent discard せず末尾へそのまま付ける。
    out_rows: list[list[str]] = []
    for row in load.rows:
        out_rows.append(
            [row.cells.get(col, "") for col in load.header] + list(row.extra_cells)
        )

    for f in applied:
        f.auto_fixed = True
    return FixResult(header=new_header, rows=out_rows, applied=applied)
