from pathlib import Path
from preflight_kit.loader import load_csv, LoadResult
from preflight_kit.models import RowKind


def _write(tmp_path: Path, name: str, content: bytes) -> str:
    p = tmp_path / name
    p.write_bytes(content)
    return str(p)


def test_load_basic_new_format(tmp_path):
    csv = (
        "Title,URL handle,SKU,Option1 name,Option1 value,Price\n"
        "Tee,tee,TEE-1,Color,Red,1000\n"
    ).encode("utf-8")
    res = load_csv(_write(tmp_path, "a.csv", csv))
    assert isinstance(res, LoadResult)
    assert res.blocked is False
    assert res.header[0] == "Title"
    assert res.rows[0].get("handle") == "tee"
    assert res.rows[0].get("title") == "Tee"
    assert res.rows[0].is_product_start is True
    assert res.rows[0].row_kind == RowKind.PRODUCT


def test_bom_detected_as_f01a(tmp_path):
    csv = ("﻿Title,URL handle\nTee,tee\n").encode("utf-8")
    res = load_csv(_write(tmp_path, "bom.csv", csv))
    ids = {f.rule_id for f in res.file_findings}
    assert "F01a" in ids
    # BOM 除去後、ヘッダーは Title（先頭に BOM が残らない）
    assert res.header[0] == "Title"


def test_non_utf8_detected_as_f01b_suggested(tmp_path):
    # cp932（Shift-JIS）。UTF-8 デコード不能を検出（推定変換はしない）
    csv = "Title,URL handle\n日本語,nihongo\n".encode("cp932")
    res = load_csv(_write(tmp_path, "sjis.csv", csv))
    ids = {f.rule_id for f in res.file_findings}
    assert "F01b" in ids


def test_multivariant_groups_share_one_product_start(tmp_path):
    csv = (
        "Title,URL handle,SKU,Option1 name,Option1 value\n"
        "Tee,tee,TEE-RED,Color,Red\n"
        ",tee,TEE-BLUE,Color,Blue\n"
    ).encode("utf-8")
    res = load_csv(_write(tmp_path, "mv.csv", csv))
    assert res.rows[0].product_group_id == res.rows[1].product_group_id
    assert res.rows[0].is_product_start is True
    assert res.rows[1].is_product_start is False
    assert res.rows[1].row_kind == RowKind.VARIANT


def test_image_row_classified(tmp_path):
    csv = (
        "Title,URL handle,Product image URL\n"
        "Tee,tee,https://x/1.jpg\n"
        ",tee,https://x/2.jpg\n"
    ).encode("utf-8")
    res = load_csv(_write(tmp_path, "img.csv", csv))
    assert res.rows[1].row_kind == RowKind.IMAGE


def test_pii_column_blocks_processing(tmp_path):
    csv = ("Title,URL handle,Customer Email\nTee,tee,a@b.com\n").encode("utf-8")
    res = load_csv(_write(tmp_path, "pii.csv", csv))
    assert res.blocked is True


def test_blank_handle_first_row_is_product_start(tmp_path):
    # handle 空でも先頭行は product-start（#1: R02 が handle 欠落を評価できる）
    csv = ("Title,URL handle\nTee,\n").encode("utf-8")
    res = load_csv(_write(tmp_path, "noh.csv", csv))
    assert res.rows[0].is_product_start is True


def test_repeated_title_same_handle_is_second_product_start(tmp_path):
    # 同一 handle で Title 反復 = 2つ目の product-start（#2: R03 が拾える）
    csv = ("Title,URL handle\nTee,tee\nTee Two,tee\n").encode("utf-8")
    res = load_csv(_write(tmp_path, "dup.csv", csv))
    assert res.rows[0].is_product_start is True
    assert res.rows[1].is_product_start is True
    assert res.rows[0].product_group_id != res.rows[1].product_group_id


def test_blank_handle_blank_title_continuation_is_variant(tmp_path):
    # handle 空 + Title 空 + 直前グループあり = variant 継続行（#3）。
    # product-start にせず、group_id を継承する。
    csv = (
        "Title,URL handle,Option1 name,Option1 value\nTee,tee,Color,Red\n,,Color,Blue\n"
    ).encode("utf-8")
    res = load_csv(_write(tmp_path, "cont.csv", csv))
    assert res.rows[1].is_product_start is False
    assert res.rows[1].row_kind == RowKind.VARIANT
    assert res.rows[1].product_group_id == res.rows[0].product_group_id


def test_no_carry_over_after_blank_handle_product(tmp_path):
    # round-2 #1 回帰: handle 空の本体行を挟んでも、後続の同一 handle 行が
    # 前グループを誤って継承しない（grp 代表 handle 基準で判定）。
    csv = ("Title,URL handle\nTee,tee\nNo Handle,\nMore,tee\n").encode("utf-8")
    res = load_csv(_write(tmp_path, "carry.csv", csv))
    # 3行とも別グループ（g1: tee本体 / g2: handle欠落本体 / g3: tee再掲本体）
    gids = [r.product_group_id for r in res.rows]
    assert len(set(gids)) == 3
    assert all(r.is_product_start for r in res.rows)


def test_extra_cells_reported_as_f04c_and_preserved(tmp_path):
    # round-1 blocking #1 回帰: ヘッダー列数を超える行（列ずれ）を silent discard
    # せず、F04c critical を出しつつ余剰セルを extra_cells に保持する。
    csv = (
        "Title,URL handle\nTee,tee,leftover-a,leftover-b\n"  # 4 セル vs 2 列
    ).encode("utf-8")
    res = load_csv(_write(tmp_path, "ragged.csv", csv))
    f04c = [f for f in res.file_findings if f.rule_id == "F04c"]
    assert len(f04c) == 1
    assert f04c[0].severity.value == "critical"
    assert f04c[0].row == 1  # ヘッダー除く1行目
    # 余剰セルは捨てずに保持
    assert res.rows[0].extra_cells == ["leftover-a", "leftover-b"]


def test_no_extra_cells_for_well_formed_row(tmp_path):
    csv = ("Title,URL handle\nTee,tee\n").encode("utf-8")
    res = load_csv(_write(tmp_path, "ok.csv", csv))
    assert res.rows[0].extra_cells == []
    assert not any(f.rule_id == "F04c" for f in res.file_findings)


def test_oversized_file_skips_parse_without_crash(tmp_path):
    # round-1 blocking #2 回帰: 15MB 超ファイルは行 parse を試みず空行で返し、
    # csv.Error でクラッシュしない（F04a は file rule が raw_byte_size から出す）。
    header = b"Title,URL handle\n"
    # 単一の巨大セル（16MB 超）を含む行。field_size_limit を超えても parse しない。
    big_cell = b"x" * (16 * 1024 * 1024)
    csv = header + b"Tee," + big_cell + b"\n"
    res = load_csv(_write(tmp_path, "big.csv", csv))
    assert res.raw_byte_size > 15 * 1024 * 1024
    assert res.rows == []  # 行 parse スキップ
    assert res.parse_skipped is True
    assert res.blocked is False  # PII の全停止とは区別（file rule は走る）
    # round-2 spec-conformance 回帰: ヘッダーは読むので Title/URL handle が canonical に
    # 入り、F03c（必須列欠落）が誤発火しない。
    assert res.header == ["Title", "URL handle"]
    assert set(res.canonical_map.values()) >= {"title", "handle"}


def test_oversized_file_with_pii_still_blocks_and_reports_f04a(tmp_path):
    # round-2 blocking(security) 回帰: 15MB 超でも PII 列はヘッダーを読んで検出し、
    # GUARD-PII で blocked=True にする（巨大 order/customer CSV でガードを迂回しない）。
    # round-3 blocking(spec-conformance) 回帰: blocked=True でも F04a(15MB hard limit)
    # は raw_byte_size だけで決まる critical なので engine 後に必ず出る（F04a の
    # false negative を防ぐ）。
    from preflight_kit.engine import run_engine
    from preflight_kit.models import ImportIntent

    header = b"Handle,Title,Customer Email,Phone\n"
    big_cell = b"x" * (16 * 1024 * 1024)
    csv = header + b"a,b,c@d.com," + big_cell + b"\n"
    res = load_csv(_write(tmp_path, "big_pii.csv", csv))
    assert res.parse_skipped is True
    assert res.blocked is True
    assert any(f.rule_id == "GUARD-PII" for f in res.file_findings)
    findings = run_engine(res, ImportIntent.MIXED)
    rule_ids = {f.rule_id for f in findings}
    assert "GUARD-PII" in rule_ids
    assert "F04a" in rule_ids  # blocked でも F04a は出る


def test_oversized_file_does_not_false_fire_f03c(tmp_path):
    # round-2 spec-conformance 回帰: handle/title を持つ巨大 product CSV で
    # F04a のみが出て、F03c（handle/title 欠落）が混入しないこと。
    from preflight_kit.engine import run_engine
    from preflight_kit.models import ImportIntent

    header = b"Handle,Title,Variant SKU\n"
    big_cell = b"x" * (16 * 1024 * 1024)
    csv = header + b"a,b," + big_cell + b"\n"
    res = load_csv(_write(tmp_path, "big_product.csv", csv))
    findings = run_engine(res, ImportIntent.MIXED)
    rule_ids = {f.rule_id for f in findings}
    assert "F04a" in rule_ids
    assert "F03c" not in rule_ids


def test_oversized_header_read_failure_skips_f03c(tmp_path):
    # round-3 non-blocking 回帰: ヘッダー行自体が field_size_limit(64MB) 超の巨大セルを
    # 含み csv.Error で読めない場合、header=[] になる。列構造が不明なので F03c は
    # 判定不能としてスキップし、F04a critical に委ねる（header=[] 起点の handle/title
    # 欠落を誤発火させない）。
    from preflight_kit.engine import run_engine
    from preflight_kit.models import ImportIntent

    giant = b"x" * (65 * 1024 * 1024)  # 64MB field_size_limit 超
    csv = giant + b",Title\n" + b"a,b\n"
    res = load_csv(_write(tmp_path, "giant_header.csv", csv))
    assert res.parse_skipped is True
    assert res.header == []  # ヘッダー read 失敗
    findings = run_engine(res, ImportIntent.MIXED)
    rule_ids = {f.rule_id for f in findings}
    assert "F04a" in rule_ids
    assert "F03c" not in rule_ids
