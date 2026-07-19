"""Golden crosscheck 用の読み取り専用 JSON dump（検査ロジックは一切変更しない）。

`load_csv` + `run_engine` を呼び、findings を TS `reporters.ts` の `NormalizedFinding`
と **同一スキーマ・同一 key 順・同一 full sort key** の JSON 配列で stdout 出力する。

TS reporters.ts の NormalizedFinding と同期（変更時は両方）:
  key order: ruleId, row, severity, field, fixClass, autoFixable,
             productGroupId, rowKind, message, suggestedFix
  sort key : ruleId, row ?? -1, severity, field ?? "", fixClass,
             productGroupId ?? "", rowKind ?? "", message, suggestedFix

使い方:
  uv run python -m preflight_kit.json_dump <input.csv> --intent <new|update|mixed>
"""

from __future__ import annotations
import argparse
import json
import sys

from .loader import load_csv
from .engine import run_engine
from .models import Finding, ImportIntent


def _enum_value(v) -> str | None:
    if v is None:
        return None
    if hasattr(v, "value"):
        return v.value
    return str(v)


def to_normalized_record(f: Finding) -> dict:
    # key 順は TS NormalizedFinding と 1:1（dict 挿入順 = JSON 出力順）。
    return {
        "ruleId": f.rule_id,
        "row": f.row,
        "severity": _enum_value(f.severity),
        "field": f.field,
        "fixClass": _enum_value(f.fix_class),
        "autoFixable": bool(f.auto_fixable),
        "productGroupId": f.product_group_id,
        "rowKind": _enum_value(f.row_kind),
        "message": f.message,
        "suggestedFix": f.suggested_fix,
    }


def normalize_findings(findings: list[Finding]) -> list[dict]:
    records = [to_normalized_record(f) for f in findings]
    # full sort key（TS normalizeFindings と同一順）。None は TS の ?? 既定に合わせる。
    records.sort(
        key=lambda r: (
            r["ruleId"],
            r["row"] if r["row"] is not None else -1,
            r["severity"],
            r["field"] if r["field"] is not None else "",
            r["fixClass"],
            r["productGroupId"] if r["productGroupId"] is not None else "",
            r["rowKind"] if r["rowKind"] is not None else "",
            r["message"],
            r["suggestedFix"],
        )
    )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preflight-kit-json-dump")
    parser.add_argument("input")
    parser.add_argument("--intent", choices=["new", "update", "mixed"], default="new")
    args = parser.parse_args(argv)

    intent = ImportIntent(args.intent)
    load = load_csv(args.input)
    findings = run_engine(load, intent)
    records = normalize_findings(findings)
    json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
