from pathlib import Path
import pytest

FIX = Path(__file__).parent / "fixtures"


def _ensure(rel: str, data: bytes) -> None:
    p = FIX / rel / "input.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


@pytest.fixture(scope="session", autouse=True)
def _binary_fixtures():
    # BOM 付き UTF-8（F01a）
    _ensure("bom_utf8", "﻿Title,URL handle\nTee,tee\n".encode("utf-8"))
    # 非 UTF-8（F01b）
    _ensure("non_utf8", "Title,URL handle\n日本語,nihongo\n".encode("cp932"))
    # 制御文字（F01c）
    _ensure("control_char", b"Title,URL handle\nTe\x07e,tee\n")
    # 15MB 超（F04a）。巨大なので毎回生成・コミットしない（.gitignore 対象）
    big = "x" * (15 * 1024 * 1024 + 10)
    _ensure(
        "over_15mb",
        ("Title,URL handle,Description\nTee,tee," + big + "\n").encode("utf-8"),
    )
    yield
