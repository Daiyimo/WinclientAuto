"""单元测试：winclient_auto.utils.csv_loader。

覆盖 load_cases 和 load_custom_cases 的核心逻辑，包括正常路径、
边界条件（空输入、缺列）和过滤逻辑。
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from winclient_auto.utils.csv_loader import load_cases, load_custom_cases


def _write_csv(tmp_path: Path, content: str) -> Path:
    """辅助函数：将 content 写入临时 CSV 文件并返回路径。"""
    p = tmp_path / "cases.csv"
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return p


# ── 正常路径 ───────────────────────────────────────────────────────────────────

class TestLoadCasesHappyPath:
    def test_loads_all_rows(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            name,expected,marks
            Alice,pass,smoke
            Bob,fail,regression
        """)
        result = load_cases(csv, columns=["name", "expected"])
        assert result == [("Alice", "pass"), ("Bob", "fail")]

    def test_auto_columns_excludes_marks(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            col_a,col_b,marks
            x,y,smoke
        """)
        result = load_cases(csv)
        assert result == [("x", "y")]

    def test_mark_filter_smoke(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            name,marks
            Alice,smoke
            Bob,regression
            Charlie,smoke,regression
        """)
        result = load_cases(csv, columns=["name"], mark_filter="smoke")
        assert ("Alice",) in result
        assert ("Bob",) not in result

    def test_mark_filter_none_returns_all(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            name,marks
            Alice,smoke
            Bob,regression
        """)
        result = load_cases(csv, columns=["name"], mark_filter=None)
        assert len(result) == 2

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        # CSV 中无引号字段的前后空白应被 strip 掉
        csv = _write_csv(tmp_path, """
            name,expected
            Alice  ,  pass
        """)
        result = load_cases(csv, columns=["name", "expected"])
        assert result == [("Alice", "pass")]

    def test_bom_utf8_compatibility(self, tmp_path: Path) -> None:
        p = tmp_path / "bom.csv"
        # Excel 导出 BOM 格式
        p.write_bytes(b"\xef\xbb\xbfname,expected\r\nAlice,pass\r\n")
        result = load_cases(p, columns=["name", "expected"])
        assert result == [("Alice", "pass")]


# ── 边界条件 ───────────────────────────────────────────────────────────────────

class TestLoadCasesEdgeCases:
    def test_skips_empty_rows(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            name,expected
            Alice,pass

            ,
        """)
        result = load_cases(csv, columns=["name", "expected"])
        assert result == [("Alice", "pass")]

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.csv"
        p.write_text("name,expected\n", encoding="utf-8")
        result = load_cases(p, columns=["name", "expected"])
        assert result == []

    def test_single_column(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            id
            001
            002
        """)
        result = load_cases(csv, columns=["id"])
        assert result == [("001",), ("002",)]


# ── 错误路径 ───────────────────────────────────────────────────────────────────

class TestLoadCasesErrors:
    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="不存在"):
            load_cases(tmp_path / "nonexistent.csv")

    def test_raises_on_missing_columns(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            name,expected
            Alice,pass
        """)
        with pytest.raises(ValueError, match="缺少必要列"):
            load_cases(csv, columns=["name", "nonexistent_col"])

    def test_raises_on_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="为空"):
            load_cases(p)


# ── load_custom_cases（向后兼容别名）──────────────────────────────────────────

class TestLoadCustomCases:
    def test_same_as_load_cases_with_columns(self, tmp_path: Path) -> None:
        csv = _write_csv(tmp_path, """
            a,b,marks
            1,2,smoke
            3,4,regression
        """)
        result1 = load_cases(csv, columns=["a", "b"], mark_filter="smoke")
        result2 = load_custom_cases(csv, columns=["a", "b"], mark_filter="smoke")
        assert result1 == result2 == [("1", "2")]
