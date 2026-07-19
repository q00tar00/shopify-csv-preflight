from __future__ import annotations

from .loader import LoadResult
from .models import Finding, ImportIntent
from .header_registry import CANONICAL_TO_HEADERS
from .rules import ALL_RULES
from .rules.file_rules import rule_f04a


def _build_field_display_map(load: LoadResult) -> dict[str, str]:
    """ルールがハードコードする primary 列名 -> その CSV で実際に使われた元列名。

    spec: errors.csv の `field` は「元の列名で表示」する。ルールは primary 名
    （例 `URL handle`/`SKU`）を field に渡すため、旧 alias 入力（例 `Handle`/
    `Variant SKU`）では実在しない列名が出てしまう（round-1 non-blocking）。
    canonical key 経由で逆引きし、実入力の列名へ置換するマップを作る。
    """
    # canonical key -> 実際の元列名。同一 canonical key に複数の元列名がある場合
    # （例 `Handle` と `URL handle` が両方 handle に対応）、loader の row.canonical は
    # header 順の dict 内包で構築され **後勝ち**（最後に現れた列の値が残る）。よって
    # ルールが実際に参照している値は最後の列のものなので、display も最後の列名を採用し
    # 整合させる（setdefault=最初優先だと値とラベルがずれる・round-2 non-blocking）。
    key_to_original: dict[str, str] = {}
    for original_col, key in load.canonical_map.items():
        key_to_original[key] = original_col  # 後勝ち（row.canonical と一致）
    # primary 名（ルールが渡す値・CANONICAL_TO_HEADERS 先頭） -> 実際の元列名。
    # primary == 実列名のとき（新形式入力）は置換不要なので除く。
    display: dict[str, str] = {}
    for key, original in key_to_original.items():
        primary = CANONICAL_TO_HEADERS.get(key, [None])[0]
        if primary is not None and primary != original:
            display[primary] = original
    return display


def run_engine(load: LoadResult, intent: ImportIntent) -> list[Finding]:
    findings: list[Finding] = list(load.file_findings)
    if load.blocked:
        # PII ガード等で停止。値・列の中身を見るルールは走らせない。
        # ただし F04a（15MB hard limit）は raw_byte_size だけで決まり、import 可否に
        # 直結する critical なので、PII 停止時でも必ず出す（round-3 blocking: 15MB 超 +
        # PII で F04a が false negative になっていた）。F04a は header/rows を参照しない
        # ため blocked 状態でも安全に評価できる。
        findings.extend(rule_f04a(load, intent))
        return findings
    # parse_skipped でヘッダーすら読めなかった（巨大セルで csv.Error）場合、列構造が
    # 不明なため F03c（必須列欠落）は判定不能。これを通常実行すると header=[] を根拠に
    # title/handle 欠落を誤発火する（round-3 non-blocking）。F04a critical に委ね、
    # 列構造が読めていない F03c はスキップする。ヘッダーが読めた parse_skipped（巨大
    # product CSV）では header 非空なので F03c は正しく機能する（列があれば出ない）。
    skip_f03c = load.parse_skipped and not load.header
    for rule in ALL_RULES:
        if skip_f03c and getattr(rule, "__name__", "") == "rule_f03c":
            continue
        findings.extend(rule(load, intent))
    # field を実入力の元列名へ正規化（spec: 元の列名で表示）。
    display = _build_field_display_map(load)
    if display:
        for f in findings:
            if f.field in display:
                f.field = display[f.field]
    return findings
