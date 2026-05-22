"""tests/conftest.py — 框架测试全局 fixture 与 pytest hooks。

Hooks 对所有测试生效（框架单元测试 + 各 App 适配层集成测试）：
  - pytest_sessionstart       写入 Allure 环境信息文件
  - pytest_runtest_makereport 测试失败时自动截图并附加到 Allure 报告
  - pytest_sessionfinish      格式化 JUnit XML 报告（补全缩进 + 还原中文转义）

App 专属 fixture（如 app / main_page）由各 App 的 conftest.py 自行定义，
本文件不包含任何业务/应用相关代码。
"""

from __future__ import annotations

import logging
import re
import sys
import xml.dom.minidom
from pathlib import Path
from typing import Any, Generator

import pytest

# 确保根目录在 sys.path，允许直接 import winclient_auto 和 apps
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


# ── Allure 报告定制 ────────────────────────────────────────────────────────────

def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    """写入 Allure 环境信息文件（在报告 Environment 面板展示）。"""
    allure_dir = Path("reports/allure-results")
    allure_dir.mkdir(parents=True, exist_ok=True)
    env_props = "\n".join([
        f"Python={sys.version.split()[0]}",
        "Project=winclient-auto",
        "Framework=Playwright CDP / pywinauto / Browser",
    ])
    (allure_dir / "environment.properties").write_text(env_props, encoding="utf-8")


# ── 失败时自动截图并附加到 Allure 报告 ────────────────────────────────────────

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[Any, None, None]:
    """测试失败时自动截图并附加到 Allure 报告，不产生任何磁盘文件。

    兼容所有继承自 BasePage 的 Page Object（持有 ``_page`` 属性），
    以及直接使用 Playwright Page 对象的 fixture。

    成功用例零开销，失败截图通过 allure.attach() 写入 allure-results，
    无论运行多少用例都不会在本地累积截图文件。
    """
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    # 遍历所有 fixture，找第一个带 screenshot 能力的对象
    # 优先 BasePage 子类（有 _page 属性），其次原生 Playwright Page（有 screenshot 方法）
    playwright_page = None
    for fixture_val in item.funcargs.values():
        if hasattr(fixture_val, "_page") and hasattr(fixture_val._page, "screenshot"):
            playwright_page = fixture_val._page
            break
        if hasattr(fixture_val, "screenshot") and callable(fixture_val.screenshot):
            # 原生 Playwright Page 也有 screenshot()，但参数不同于 BasePage
            if hasattr(fixture_val, "url"):
                playwright_page = fixture_val
                break

    if playwright_page is None:
        return

    try:
        import allure  # noqa: PLC0415

        img_bytes: bytes = playwright_page.screenshot()
        allure.attach(
            img_bytes,
            name="失败截图",
            attachment_type=allure.attachment_type.PNG,
        )
        logger.info("失败截图已附加到 Allure 报告")
    except Exception as exc:
        logger.debug("失败截图附加失败: %s", exc)


# ── 测试结束后格式化 JUnit XML 报告 ────────────────────────────────────────────

def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG001
    """将 JUnit XML 报告格式化：补全缩进 + 还原 Unicode 转义（如中文字符）。"""
    xml_path = Path(__file__).parent.parent / "reports" / "results.xml"
    if not xml_path.exists():
        return

    try:
        content = xml_path.read_text(encoding="utf-8")

        # 将 \uXXXX 字面转义还原为真实 Unicode 字符（如 已结束 → 已结束）
        content = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1), 16)),
            content,
        )

        # 用 minidom 格式化，生成带缩进的 XML
        dom = xml.dom.minidom.parseString(content.encode("utf-8"))
        pretty = dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

        # 去除 minidom 产生的多余空行
        lines = [line for line in pretty.splitlines() if line.strip()]
        xml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.debug("JUnit XML 报告已格式化：%s", xml_path)

    except Exception as exc:
        logger.warning("格式化 JUnit XML 报告失败：%s", exc)
