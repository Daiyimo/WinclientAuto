"""WinClientApp — Windows 客户端自动化抽象基类。

所有具体的 Windows 客户端驱动（Electron、Win32 原生、浏览器）
必须继承此类并实现全部抽象方法，从而对调用方（CLI、pytest fixtures、agent）
提供统一的接口。

用法示例::

    from winclient_auto.core.electron_app import ElectronApp

    class MyApp(ElectronApp):
        def __init__(self):
            super().__init__(exe_path="C:/App/app.exe", process_name="app")

    app = MyApp()
    app.launch()
    page = app.page
    app.close()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WinClientApp(ABC):
    """Windows 客户端自动化抽象基类。

    子类需实现 :meth:`launch`、:meth:`connect`、:meth:`close`、:attr:`page`。
    :meth:`kill` 提供默认实现（close + 杀进程），子类可按需覆盖。
    """

    # ── 连接方式 ─────────────────────────────────────────────────────────────

    @abstractmethod
    def launch(self) -> "WinClientApp":
        """启动应用并建立自动化连接。

        实现应包含：
        1. 终止已有实例（幂等）
        2. 以调试/自动化模式启动应用
        3. 等待应用就绪
        4. 建立自动化连接（CDP / UIA / Playwright）

        Returns:
            self，支持链式调用。
        """
        ...

    @abstractmethod
    def connect(self) -> "WinClientApp":
        """连接到已运行的应用实例（不重新启动）。

        Returns:
            self，支持链式调用。

        Raises:
            RuntimeError: 应用未运行或连接失败。
        """
        ...

    # ── 页面访问 ─────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def page(self) -> Any:
        """返回当前主页面/应用对象。

        - Electron / Browser：返回 ``playwright.sync_api.Page``
        - Win32 原生：返回 ``pywinauto.application.Application``

        Raises:
            RuntimeError: 尚未调用 :meth:`launch` 或 :meth:`connect`。
        """
        ...

    # ── 生命周期 ─────────────────────────────────────────────────────────────

    @abstractmethod
    def close(self) -> None:
        """断开自动化连接（不终止应用进程）。"""
        ...

    def kill(self) -> None:
        """断开连接并强制终止应用进程。

        默认实现：先 :meth:`close`，再按进程名 kill。
        子类若需自定义 kill 逻辑可覆盖此方法。
        """
        self.close()
        if hasattr(self, "_process_name") and self._process_name:
            from winclient_auto.utils.process import kill_processes  # noqa: PLC0415

            kill_processes(self._process_name)
