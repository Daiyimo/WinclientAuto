"""通用 pytest fixtures。

提供可被任意 Windows 客户端测试直接复用的 fixture 集合。
使用方式：在各应用的 ``conftest.py`` 中导入，或在 ``pyproject.toml``
中注册为 ``pytest11`` 插件入口点（自动加载，无需手动导入）。

典型用法::

    # tests/conftest.py（应用项目中）
    from winclient_auto.pytest_plugin.fixtures import (
        inter_test_delay,
        make_winclient_fixtures,
    )

    # 用工厂函数生成与具体 App 绑定的 fixtures
    app_fixture, page_fixture = make_winclient_fixtures(
        lambda: MyApp()
    )
    app = app_fixture
    page = page_fixture
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Generator

import pytest

from winclient_auto.core.base_app import WinClientApp

logger = logging.getLogger(__name__)

# 全局默认用例间隔（秒），可由环境变量 WCA_TEST_DELAY 覆盖
_DEFAULT_TEST_DELAY: float = 3.0


def make_winclient_fixtures(
    app_factory: Callable[[], WinClientApp],
    scope: str = "session",
) -> tuple[Any, Any]:
    """工厂函数：为指定应用创建 app 和 page 两个 fixtures。

    生成的 fixtures 可直接赋值给模块级变量，再被 pytest 发现。

    Args:
        app_factory: 无参可调用对象，返回已配置的 WinClientApp 实例。
        scope: app fixture 的作用域（``"session"``、``"module"``、``"function"``），
               默认 ``"session"``（整个测试会话共享一个实例）。

    Returns:
        ``(app_fixture, page_fixture)`` 两个 pytest fixture 函数。

    Examples:
        >>> app, page = make_winclient_fixtures(lambda: MyApp())
        >>> # 将返回值赋值给 conftest 模块级变量即可让 pytest 发现
    """

    @pytest.fixture(scope=scope)
    def winclient_app() -> Generator[WinClientApp, None, None]:
        """启动应用，会话结束后自动关闭。"""
        app = app_factory()
        app.launch()
        yield app
        app.close()

    @pytest.fixture
    def winclient_page(winclient_app: WinClientApp) -> Any:
        """返回当前 app 的主页面对象。"""
        return winclient_app.page

    return winclient_app, winclient_page


@pytest.fixture(autouse=True)
def inter_test_delay() -> Generator[None, None, None]:
    """每个 test 执行完毕后等待一段时间，避免 UI 操作过快造成状态污染。

    间隔秒数由环境变量 ``WCA_TEST_DELAY`` 控制，默认 3s。
    开发冒烟时可设为 1s：``WCA_TEST_DELAY=1 pytest -m smoke``。
    """
    yield
    delay = float(os.environ.get("WCA_TEST_DELAY", str(_DEFAULT_TEST_DELAY)))
    if delay > 0:
        time.sleep(delay)
