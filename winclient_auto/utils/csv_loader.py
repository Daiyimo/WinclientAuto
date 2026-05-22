"""通用 CSV 测试数据加载器。

将 CSV 文件转换为 ``pytest.mark.parametrize`` 兼容的参数元组列表，
支持自定义列名和 mark 过滤，与具体业务字段完全解耦。

CSV 格式约定（marks 列可选）：

    col_a,col_b,col_c,marks
    value1,value2,value3,smoke
    value4,value5,value6,smoke,regression

用法示例::

    from pathlib import Path
    from winclient_auto.utils.csv_loader import load_cases, load_custom_cases

    # 方式1：加载指定列（顺序即元组顺序）
    cases = load_cases(
        Path("data/run_cases.csv"),
        columns=["run_name", "expected_status"],
        mark_filter="smoke",
    )

    # 方式2：加载全部列（除 marks 列外）
    all_cases = load_cases(Path("data/cases.csv"))
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def load_cases(
    csv_path: Path,
    columns: list[str] | None = None,
    mark_filter: str | None = None,
) -> list[tuple[Any, ...]]:
    """从 CSV 文件加载测试数据，返回 parametrize 兼容的元组列表。

    Args:
        csv_path: CSV 文件路径。
        columns: 要读取的列名列表；若为 ``None``，则读取除 ``marks`` 以外的全部列。
        mark_filter: 仅返回 marks 列包含该标签的行（``None`` 表示不过滤）。

    Returns:
        每个元素为一个 ``tuple``，顺序与 ``columns`` 一致。

    Raises:
        FileNotFoundError: CSV 文件不存在。
        ValueError: CSV 缺少 ``columns`` 中指定的列。

    Examples:
        >>> load_cases(Path("data/cases.csv"), columns=["name", "expected"])
        [('Alice', 'pass'), ('Bob', 'fail')]
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 数据文件不存在: {csv_path}")

    results: list[tuple[Any, ...]] = []

    with csv_path.open(encoding="utf-8-sig") as f:  # utf-8-sig 兼容 Excel 导出 BOM
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"CSV 文件为空: {csv_path}")

        # 确定要读取的列
        all_fields = list(reader.fieldnames)
        if columns is None:
            columns = [c for c in all_fields if c.strip().lower() != "marks"]

        missing = set(columns) - set(all_fields)
        if missing:
            raise ValueError(
                f"CSV 缺少必要列: {missing}\n"
                f"当前列: {all_fields}"
            )

        for row in reader:
            # 跳过全空行
            if not any(row.get(c, "").strip() for c in columns):
                continue

            # mark 过滤
            if mark_filter is not None:
                row_marks = {m.strip() for m in row.get("marks", "").split(",")}
                if mark_filter not in row_marks:
                    continue

            results.append(tuple(row[c].strip() for c in columns))

    return results


def load_custom_cases(
    csv_path: Path,
    columns: list[str],
    mark_filter: str | None = None,
) -> list[tuple[Any, ...]]:
    """``load_cases`` 的别名，显式要求传入列名。

    Args:
        csv_path: CSV 文件路径。
        columns: 要读取的列名列表，顺序即元组顺序。
        mark_filter: marks 列过滤标签，``None`` 表示不过滤。

    Returns:
        pytest.mark.parametrize 兼容的元组列表。
    """
    return load_cases(csv_path, columns=columns, mark_filter=mark_filter)
