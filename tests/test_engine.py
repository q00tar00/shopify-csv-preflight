from csv_preflight.loader import LoadResult
from csv_preflight.models import Row, RowKind, Severity, FixClass, Finding, ImportIntent
from csv_preflight.engine import run_engine


def _load(header, rows, file_findings=None, blocked=False):
    return LoadResult(
        header=header,
        rows=rows,
        canonical_map={c: c for c in []},
        file_findings=file_findings or [],
        encoding="utf-8",
        raw_byte_size=10,
        blocked=blocked,
    )


def test_engine_includes_loader_file_findings():
    f = Finding(
        row=None,
        product_group_id=None,
        row_kind=None,
        handle=None,
        sku=None,
        severity=Severity.CRITICAL,
        rule_id="F01a",
        field=None,
        message="m",
        suggested_fix="s",
        fix_class=FixClass.PROVEN,
        auto_fixable=True,
    )
    findings = run_engine(_load(["Title"], [], file_findings=[f]), ImportIntent.MIXED)
    assert any(x.rule_id == "F01a" for x in findings)


def test_engine_stops_when_blocked():
    f = Finding(
        row=None,
        product_group_id=None,
        row_kind=None,
        handle=None,
        sku=None,
        severity=Severity.CRITICAL,
        rule_id="GUARD-PII",
        field="Customer Email",
        message="m",
        suggested_fix="s",
        fix_class=FixClass.NONE,
        auto_fixable=False,
    )
    findings = run_engine(
        _load(["Customer Email"], [], file_findings=[f], blocked=True),
        ImportIntent.MIXED,
    )
    # blocked のときは file_findings のみ（ルールは走らせない）
    assert [x.rule_id for x in findings] == ["GUARD-PII"]


def test_engine_runs_row_rules():
    row = Row(
        line_no=1,
        cells={"URL handle": "tee"},
        canonical={"handle": "tee"},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    findings = run_engine(_load(["URL handle"], [row]), ImportIntent.NEW)
    # title 欠落で R01 critical が出る
    assert any(x.rule_id == "R01" and x.severity == Severity.CRITICAL for x in findings)


def test_engine_field_uses_original_legacy_column_name():
    # round-1 non-blocking #1 回帰: 旧 alias 入力（Handle）では errors.csv の field を
    # primary 名（URL handle）でなく実入力列名（Handle）で表示する（spec: 元の列名）。
    row = Row(
        line_no=1,
        cells={"Handle": ""},  # handle 値が空 -> R02 が handle 欠落を出す
        canonical={"handle": ""},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    load = LoadResult(
        header=["Handle"],
        rows=[row],
        canonical_map={"Handle": "handle"},  # 旧 alias 入力
        file_findings=[],
        encoding="utf-8",
        raw_byte_size=10,
        blocked=False,
    )
    findings = run_engine(load, ImportIntent.UPDATE)
    r02 = [f for f in findings if f.rule_id == "R02"]
    assert r02, "R02 (handle 欠落) が出るはず"
    # field は primary 'URL handle' でなく実入力 'Handle'
    assert all(f.field == "Handle" for f in r02)


def test_engine_field_unchanged_for_new_format():
    # 新形式入力（URL handle）では置換が起きず primary 名のまま。
    row = Row(
        line_no=1,
        cells={"URL handle": ""},
        canonical={"handle": ""},
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    load = LoadResult(
        header=["URL handle"],
        rows=[row],
        canonical_map={"URL handle": "handle"},
        file_findings=[],
        encoding="utf-8",
        raw_byte_size=10,
        blocked=False,
    )
    findings = run_engine(load, ImportIntent.UPDATE)
    r02 = [f for f in findings if f.rule_id == "R02"]
    assert r02 and all(f.field == "URL handle" for f in r02)


def test_engine_field_duplicate_canonical_uses_last_column():
    # round-2 non-blocking 回帰: 同一 canonical key に複数の元列名がある場合
    # （Handle と URL handle が両方 handle）、loader の row.canonical は header 順の
    # 後勝ちで最後の列(URL handle)の値を取る。field 表示も最後の列名に整合させ、
    # 「ルールが見ている値」と「表示ラベル」がずれないこと。
    row = Row(
        line_no=1,
        cells={"Handle": "", "URL handle": ""},
        canonical={"handle": ""},  # 後勝ちで URL handle の値（空）
        product_group_id="g1",
        row_kind=RowKind.PRODUCT,
        is_product_start=True,
    )
    load = LoadResult(
        header=["Handle", "URL handle"],
        rows=[row],
        # 挿入順 = header 順。後勝ち列は URL handle。
        canonical_map={"Handle": "handle", "URL handle": "handle"},
        file_findings=[],
        encoding="utf-8",
        raw_byte_size=10,
        blocked=False,
    )
    findings = run_engine(load, ImportIntent.UPDATE)
    r02 = [f for f in findings if f.rule_id == "R02"]
    assert r02, "R02 (handle 欠落) が出るはず"
    # row.canonical が値を取る最後の列(URL handle)に整合
    assert all(f.field == "URL handle" for f in r02)
