from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

# Shopify product CSV import の 15MB hard limit（F04a / loader の parse スキップ判定で共有）。
# loader と file_rules の双方が参照するため、依存末端の models に SoT を置く。
MAX_IMPORT_BYTES = 15 * 1024 * 1024


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class FixClass(str, Enum):
    PROVEN = "proven"
    SUGGESTED = "suggested"
    NONE = "none"


class RowKind(str, Enum):
    PRODUCT = "product"
    VARIANT = "variant"
    IMAGE = "image"


class ImportIntent(str, Enum):
    NEW = "new"
    UPDATE = "update"
    MIXED = "mixed"


@dataclass
class Row:
    """1 CSV データ行。canonical アクセスは get(key) 経由。"""

    line_no: int  # 元CSV行番号（1始まり・ヘッダー除く）
    cells: dict[str, str]  # 元の列名 -> 値（列順は header で保持）
    canonical: dict[str, str]  # canonical key -> 値（解釈用）
    product_group_id: str | None = None
    row_kind: RowKind | None = None
    is_product_start: bool = False
    # ヘッダー列数を超えた余剰セル（F04c 列ずれ行）。silent discard せず保持し、
    # fixer が出力行の末尾へそのまま付ける。通常行は空リスト。
    extra_cells: list[str] = field(default_factory=list)

    def get(self, canonical_key: str) -> str | None:
        return self.canonical.get(canonical_key)


@dataclass
class Finding:
    row: int | None
    product_group_id: str | None
    row_kind: RowKind | None
    handle: str | None
    sku: str | None
    severity: Severity
    rule_id: str
    field: str | None
    message: str
    suggested_fix: str
    fix_class: FixClass
    auto_fixable: bool
    auto_fixed: bool = False
