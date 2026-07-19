from __future__ import annotations
import csv
import io
import re
from dataclasses import dataclass, field

from .models import Finding, Row, RowKind, Severity, FixClass, MAX_IMPORT_BYTES
from .header_registry import to_canonical

# csv のフィールド長上限（既定 131072）は Shopify の長い description セルや
# 15MB 超の単一セル（F04a fixture）で `field larger than field limit` を起こす。
# Shopify の 15MB import 上限を超える 64MB に引き上げ、構造検査を最後まで走らせる。
csv.field_size_limit(64 * 1024 * 1024)

_PII_PATTERNS = [
    re.compile(r"e-?mail", re.IGNORECASE),
    re.compile(r"\bphone\b", re.IGNORECASE),
    re.compile(r"telephone", re.IGNORECASE),
    re.compile(r"address", re.IGNORECASE),
    re.compile(r"\bcustomer\b", re.IGNORECASE),
]


@dataclass
class LoadResult:
    header: list[str]
    rows: list[Row]
    canonical_map: dict[str, str]
    file_findings: list[Finding]
    encoding: str
    raw_byte_size: int
    blocked: bool = False
    # 15MB 超で行 parse をスキップしたか。header は読めていても rows は空になる。
    # CLI はこのとき fixed_products.csv を書かない（空ファイルでの元データ破壊を防ぐ）。
    # engine はこのとき行ルール・F03c 等の「行/列の中身」判定をスキップする
    # （header=[] でないので F03c 誤発火しないが、行が無い前提のルールも抑止する）。
    parse_skipped: bool = False


def _file_finding(
    rule_id, severity, message, suggested_fix, fix_class, field_name=None, row=None
):
    return Finding(
        row=row,
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


def _detect_pii(header: list[str]) -> list[Finding]:
    out = []
    for col in header:
        if any(p.search(col) for p in _PII_PATTERNS):
            out.append(
                _file_finding(
                    "GUARD-PII",
                    Severity.CRITICAL,
                    f"Buyer-PII-like column detected: '{col}'. Processing stopped (order/customer CSV out of scope).",
                    "Remove buyer PII columns; this tool only handles product CSV.",
                    FixClass.NONE,
                    field_name=col,
                )
            )
    return out


def _is_product_start(
    canonical: dict[str, str], handle: str, current_group_handle: str | None
) -> bool:
    """product-start 判定（#1/#2/#3 対応）。

    `current_group_handle` は「現在のグループの代表 handle」（最後に product-start を
    立てた行の handle 値。まだ1つもグループが無ければ None）。直前行の生 handle ではなく
    **グループ代表 handle** と比較することで、handle 空の本体行を挟んでも後続の同一 handle
    行が誤って前グループを継承する carry-over を防ぐ（round-2 #1）。

    分岐:
    - handle 非空 かつ グループ代表 handle と異なる → 新グループの product-start。
    - handle 非空 かつ グループ代表 handle と同一 → Title 非空なら 2つ目の
      product-start（R03 が拾う重複本体行）。Title 空なら variant/image（正常な反復）。
    - handle 空 かつ Title 非空 → 本体行で handle 値だけ欠落 = product-start として扱い、
      R02 が handle 欠落 severity を intent 別に判定する。
    - handle 空 かつ Title 空 かつ 直前にグループあり → 親 handle を書き忘れた
      variant/image 継続行とみなし product-start にしない（R02 の variant 分岐が
      「handle 欠落 = critical」を出せる）。直前グループが無ければ product-start。
    """
    title = (canonical.get("title") or "").strip()
    if handle != "":
        if handle != current_group_handle:
            return True
        return title != ""  # 同一グループ handle 継続
    # handle 空
    if title != "":
        return True  # 本体行で handle 値だけ欠落（R02 が intent 別に判定）
    # handle 空 かつ Title 空: 直前にグループがあれば継続行（handle 欠落 variant/image）
    return current_group_handle is None


def _classify_row(canonical: dict[str, str], is_start: bool) -> RowKind:
    if is_start:
        return RowKind.PRODUCT
    title = (canonical.get("title") or "").strip()
    has_image = bool((canonical.get("image_src") or "").strip())
    has_option = bool(
        (canonical.get("option1_value") or "").strip()
        or (canonical.get("sku") or "").strip()
        or (canonical.get("price") or "").strip()
    )
    # image 判定を variant より先に評価（spec Task1 Step2 の優先順位）
    if not title and has_image and not has_option:
        return RowKind.IMAGE
    return RowKind.VARIANT


def load_csv(path: str) -> LoadResult:
    with open(path, "rb") as fh:
        raw = fh.read()
    raw_byte_size = len(raw)
    file_findings: list[Finding] = []

    # --- F01a: BOM ---
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    if had_bom:
        raw = raw[3:]
        file_findings.append(
            _file_finding(
                "F01a",
                Severity.CRITICAL,
                "UTF-8 BOM detected at file start.",
                "BOM removed automatically.",
                FixClass.PROVEN,
            )
        )

    # --- F01b: UTF-8 デコード可否（推定変換しない） ---
    encoding = "utf-8"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        encoding = "unknown"
        file_findings.append(
            _file_finding(
                "F01b",
                Severity.CRITICAL,
                "File is not valid UTF-8 (encoding guess required).",
                "Re-export the CSV as UTF-8; this tool does not guess-convert encodings.",
                FixClass.SUGGESTED,
            )
        )
        # デコードできた範囲だけ replace で読み、構造検査は継続
        text = raw.decode("utf-8", errors="replace")

    # --- 巨大ファイルは行 parse をスキップ（F04a は file_rules が出す） ---
    # csv.reader は field_size_limit(64MB) を超える単一セルで csv.Error を投げて
    # クラッシュし、F04a critical Finding / errors.csv / report.md / exit code 1 に
    # 到達しなくなる。単一セルはファイル全体以下なので、64MB 超セルが起きるのは
    # 必ず raw_byte_size > 15MB(_MAX_BYTES) のとき。よって 15MB 超過ファイルは
    # **行**の parse を試みず parse_skipped=True で返し、F04a は後段の rule_f04a が
    # raw_byte_size から出す（ここで F04a を出すと file_rules と二重発火するため出さない）。
    #
    # ただしヘッダー 1 行だけは読む（round-2 修正）。ヘッダーを読まないと:
    #  (1) 巨大 order/customer CSV で PII ガードを迂回する（security blocking）
    #  (2) header=[] のため F03c が handle/title 欠落を誤発火する（spec-conformance）
    # ヘッダー行に巨大セルがあって read 自体が失敗する場合は header=[] のまま続行する。
    parse_skipped = raw_byte_size > MAX_IMPORT_BYTES
    if parse_skipped:
        header: list[str] = []
        try:
            header = next(csv.reader(io.StringIO(text)))
        except (StopIteration, csv.Error):
            header = []
        # ヘッダーが読めたら PII 判定は必ず通す（巨大ファイルでも安全境界を外さない）。
        pii = _detect_pii(header)
        if pii:
            file_findings.extend(pii)
            return LoadResult(
                header,
                [],
                {},
                file_findings,
                encoding,
                raw_byte_size,
                blocked=True,
                parse_skipped=True,
            )
        canonical_map = {
            col: to_canonical(col) for col in header if to_canonical(col) is not None
        }
        return LoadResult(
            header=header,
            rows=[],
            canonical_map=canonical_map,
            file_findings=file_findings,
            encoding=encoding,
            raw_byte_size=raw_byte_size,
            blocked=False,
            parse_skipped=True,
        )

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return LoadResult(
            [], [], {}, file_findings, encoding, raw_byte_size, blocked=False
        )

    # --- PII ガード ---
    pii = _detect_pii(header)
    if pii:
        file_findings.extend(pii)
        return LoadResult(
            header, [], {}, file_findings, encoding, raw_byte_size, blocked=True
        )

    canonical_map: dict[str, str] = {}
    for col in header:
        key = to_canonical(col)
        if key is not None:
            canonical_map[col] = key

    rows: list[Row] = []
    line_no = 0
    group_seq = 0
    group_id: str | None = None
    # 現在のグループ代表 handle（最後に product-start を立てた行の handle 値）。
    # 直前行の生 handle ではなくこれと比較する（carry-over 防止・round-2 #1）。
    current_group_handle: str | None = None
    for raw_cells in reader:
        line_no += 1
        cells = {
            header[i]: (raw_cells[i] if i < len(raw_cells) else "")
            for i in range(len(header))
        }
        # --- F04c: 行のセル数がヘッダー列数を超過（列ずれ） ---
        # 未クォートのカンマや壊れた行で起きる。余剰セルは silently discard せず
        # extra_cells に保持し（fixer が末尾へ出力）、critical Finding で報告する。
        extra_cells: list[str] = []
        if len(raw_cells) > len(header):
            extra_cells = list(raw_cells[len(header) :])
            file_findings.append(
                _file_finding(
                    "F04c",
                    Severity.CRITICAL,
                    f"Row {line_no} has {len(raw_cells)} cells, more than the "
                    f"{len(header)} header columns (column misalignment).",
                    "Fix the row's quoting/delimiters so cell count matches the header.",
                    FixClass.NONE,
                    row=line_no,
                )
            )
        canonical = {
            canonical_map[col]: val
            for col, val in cells.items()
            if col in canonical_map
        }
        handle = (canonical.get("handle") or "").strip()
        is_start = _is_product_start(canonical, handle, current_group_handle)
        if is_start:
            # product-start ごとに新グループ採番。同一 handle に複数 start が
            # あれば別グループになり、R03 が複数本体行を検知できる。
            group_seq += 1
            group_id = f"g{group_seq}"
            # グループ代表 handle を更新（本体行 handle 欠落時は空文字で記録）。
            current_group_handle = handle
        # 継続行（is_start=False）は group_id / current_group_handle を維持し継承する。
        kind = _classify_row(canonical, is_start)
        rows.append(
            Row(
                line_no=line_no,
                cells=cells,
                canonical=canonical,
                product_group_id=group_id,
                row_kind=kind,
                is_product_start=is_start,
                extra_cells=extra_cells,
            )
        )

    return LoadResult(
        header, rows, canonical_map, file_findings, encoding, raw_byte_size
    )
