from pathlib import Path
from preflight_kit.cli import main


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _write_bytes(tmp_path, name, data: bytes):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_clean_csv_exit_zero_and_outputs(tmp_path):
    src = _write(
        tmp_path,
        "ok.csv",
        "Title,URL handle,SKU,Option1 name,Option1 value,Price\n"
        "Tee,tee,TEE-1,Color,Red,1000\n",
    )
    out = tmp_path / "out"
    code = main(["check", src, "--out-dir", str(out), "--intent", "new"])
    assert code == 0
    assert (out / "errors.csv").exists()
    assert (out / "report.md").exists()
    assert (out / "fixed_products.csv").exists()


def test_missing_title_new_intent_exit_one(tmp_path):
    src = _write(tmp_path, "bad.csv", "Title,URL handle\n,tee\n")
    out = tmp_path / "out"
    code = main(["check", src, "--out-dir", str(out), "--intent", "new"])
    assert code == 1  # R01 critical


def test_no_fix_skips_fixed_csv(tmp_path):
    src = _write(tmp_path, "ok.csv", "Title,URL handle\nTee,tee\n")
    out = tmp_path / "out"
    code = main(["check", src, "--out-dir", str(out), "--no-fix"])
    assert code == 0
    assert not (out / "fixed_products.csv").exists()
    assert (out / "errors.csv").exists()


def test_mixed_intent_missing_title_is_warning_exit_zero(tmp_path):
    src = _write(tmp_path, "m.csv", "Title,URL handle\n,tee\n")
    out = tmp_path / "out"
    code = main(["check", src, "--out-dir", str(out), "--intent", "mixed"])
    assert code == 0  # mixed では Title 欠落は warning


def test_non_utf8_does_not_write_fixed_csv(tmp_path):
    # F01b（非 UTF-8）入力では fixed_products.csv を出さない（#7: 元データ非破壊）
    src = _write_bytes(
        tmp_path, "sjis.csv", "Title,URL handle\n日本語,nihongo\n".encode("cp932")
    )
    out = tmp_path / "out"
    code = main(["check", src, "--out-dir", str(out), "--intent", "new"])
    assert code == 1  # F01b critical
    assert not (out / "fixed_products.csv").exists()
    assert (out / "errors.csv").exists()
    assert (out / "report.md").exists()


def test_oversized_file_does_not_write_empty_fixed_csv(tmp_path):
    # round-2 blocking(correctness) 回帰: 15MB 超で行未 parse のとき fixed_products.csv を
    # 出さない。rows=[] で書くと元 CSV を空ファイルへ置き換えデータ破損になるため。
    header = "Handle,Title,Variant SKU\n"
    big_cell = "x" * (16 * 1024 * 1024)
    src = _write(tmp_path, "big.csv", header + f"a,b,{big_cell}\n")
    out = tmp_path / "out"
    code = main(["check", src, "--out-dir", str(out), "--intent", "new"])
    assert code == 1  # F04a critical
    assert not (out / "fixed_products.csv").exists()
    assert (out / "errors.csv").exists()
    assert (out / "report.md").exists()


def test_errors_csv_reflects_auto_fixed_true(tmp_path):
    # round-5 #1: case-only header の F03a は proven 適用され、errors.csv の
    # auto_fixed が true になる（apply_fixes が write_errors_csv より先に走る）
    import csv as _csv

    src = _write(tmp_path, "case.csv", "Title,url handle\nTee,tee\n")
    out = tmp_path / "out"
    main(["check", src, "--out-dir", str(out), "--intent", "new"])
    with open(out / "errors.csv", newline="", encoding="utf-8") as fh:
        rows = list(_csv.DictReader(fh))
    f03a = [r for r in rows if r["rule_id"] == "F03a"]
    assert f03a and f03a[0]["auto_fixed"] == "True"
