from pathlib import Path
from csv_preflight.cli import main

SAMPLE = (
    Path(__file__).parents[1]
    / "examples"
    / "inputs"
    / "shopify-product-import-sample.csv"
)


def test_sample_csv_runs_end_to_end(tmp_path):
    out = tmp_path / "out"
    code = main(
        ["check", str(SAMPLE), "--out-dir", str(out), "--lang", "en", "--intent", "new"]
    )
    assert code in (0, 1)  # 例外で落ちないこと
    assert (out / "errors.csv").exists()
    assert (out / "report.md").exists()
    assert (out / "fixed_products.csv").exists()
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "Not checked" in report  # 未検査範囲が必ず明記される
