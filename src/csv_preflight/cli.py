from __future__ import annotations
import argparse
import csv
import os

from .loader import load_csv
from .engine import run_engine
from .fixer import apply_fixes
from .reporters import write_errors_csv, render_report_md
from .models import Severity, ImportIntent


def _write_fixed_csv(header, rows, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="csv-preflight")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Validate a Shopify product CSV")
    check.add_argument("input")
    check.add_argument("--out-dir", default="./out")
    check.add_argument("--lang", choices=["ja", "en"], default="ja")
    check.add_argument("--no-fix", action="store_true")
    check.add_argument("--intent", choices=["new", "update", "mixed"], default="mixed")
    args = parser.parse_args(argv)

    intent = ImportIntent(args.intent)
    load = load_csv(args.input)
    findings = run_engine(load, intent)

    os.makedirs(args.out_dir, exist_ok=True)

    # fixer を errors.csv 書き込みより**先**に走らせる。apply_fixes は適用済み Finding を
    # auto_fixed=True に mutate するため、errors.csv にその最終状態を反映させる（round-5 #1）。
    # F01b（非 UTF-8）検出時は fixed_products.csv を出さない。loader は replace 文字で
    # デコードしているため、そのまま書き出すと元データを破壊する（#7）。
    # parse_skipped（15MB 超で行未 parse）時も出さない。rows=[] のまま書くと元 CSV を
    # 空ファイルへ置き換えてしまい、ユーザーが F04a critical を見落として空 fixed を
    # 使うとデータ破損になる（round-2 blocking）。F04a で import 不可なので fixed 不要。
    non_utf8 = load.encoding == "unknown"
    applied = []
    if not args.no_fix and not load.blocked and not non_utf8 and not load.parse_skipped:
        fix = apply_fixes(load, findings)
        applied = fix.applied
        _write_fixed_csv(
            fix.header, fix.rows, os.path.join(args.out_dir, "fixed_products.csv")
        )

    # auto_fixed 状態が確定してから errors.csv を書く。
    write_errors_csv(findings, os.path.join(args.out_dir, "errors.csv"))

    group_count = len({r.product_group_id for r in load.rows if r.product_group_id})
    report = render_report_md(
        findings,
        lang=args.lang,
        scanned_rows=len(load.rows),
        group_count=group_count,
        applied=applied,
    )
    with open(os.path.join(args.out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report)

    has_critical = any(f.severity == Severity.CRITICAL for f in findings)
    return 1 if has_critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
