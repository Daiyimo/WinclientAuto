"""ElectronApp — 基于 Playwright CDP 的 Electron 应用驱动。

Electron 应用使用 Chromium 渲染 UI，可通过 ``--remote-debugging-port`` 参数
暴露 CDP 端点，Playwright 经此获得完整 DOM 操作能力。

本类将 Electron CDP 自动化能力完全参数化，可驱动任意 Electron 应用。

用法示例::

    from winclient_auto.core.electron_app import ElectronApp

    app = ElectronApp(
        exe_path=r"C:\\MyApp\\MyApp.exe",
        process_name="MyApp",
        cdp_port=9222,
        loading_route="#/loading",   # 等待离开该路由才算加载完
    )
    app.launch()
    page = app.page
    page.click("button:has-text('开始')")
    app.close()
"""

from __future__ import annotations

import logging
import subprocess
import sys

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from winclient_auto.core.base_app import WinClientApp
from winclient_auto.utils.cdp import is_cdp_available, wait_for_cdp_endpoint
from winclient_auto.utils.process import kill_processes

logger = logging.getLogger(__name__)

# Playwright page action 默认超时（毫秒）
_DEFAULT_ACTION_TIMEOUT_MS: int = 10_000

# 等待主 UI 加载完成的默认超时（毫秒）
_DEFAULT_APP_LOAD_TIMEOUT_MS: int = 20_000

# CDP 端点就绪等待默认超时（秒）
_DEFAULT_CDP_CONNECT_TIMEOUT: int = 15

# 加载完成后额外等待（毫秒），确保 React/Vue 渲染稳定
_POST_LOAD_SETTLE_MS: int = 1500


class ElectronApp(WinClientApp):
    """通过 Playwright CDP 驱动任意 Electron 应用。

    Args:
        exe_path: 应用可执行文件绝对路径。
        process_name: 进程名称片段，用于 kill（如 ``"MyApp"``、``"Chrome"``）。
        cdp_port: CDP 调试端口，默认 9222。
        loading_route: 应用加载时的路由片段（如 ``"#/loading"``）；
                       若指定，则等待 URL 不再包含该片段才认为加载完成；
                       若为 ``None`` 则跳过路由等待。
        action_timeout_ms: Playwright 操作默认超时（毫秒），默认 10000。
        app_load_timeout_ms: 等待主 UI 加载的超时（毫秒），默认 20000。
        cdp_connect_timeout: 等待 CDP 端点就绪的超时（秒），默认 15。
    """

    def __init__(
        self,
        exe_path: str,
        process_name: str,
        cdp_port: int = 9222,
        loading_route: str | None = None,
        action_timeout_ms: int = _DEFAULT_ACTION_TIMEOUT_MS,
        app_load_timeout_ms: int = _DEFAULT_APP_LOAD_TIMEOUT_MS,
        cdp_connect_timeout: int = _DEFAULT_CDP_CONNECT_TIMEOUT,
    ) -> None:
        self._exe_path = exe_path
        self._process_name = process_name
        self._cdp_port = cdp_port
        self._loading_route = loading_route
        self._action_timeout_ms = action_timeout_ms
        self._app_load_timeout_ms = app_load_timeout_ms
        self._cdp_connect_timeout = cdp_connect_timeout

        self._endpoint = f"http://localhost:{cdp_port}"
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ── 连接方式 ─────────────────────────────────────────────────────────────

    def launch(self) -> "ElectronApp":
        """终止已有进程，以 CDP 调试端口重新启动，并等待 UI 就绪。

        Returns:
            self，支持链式调用。
        """
        logger.info("Killing existing '%s' processes...", self._process_name)
        kill_processes(self._process_name)

        logger.info("Launching: %s --remote-debugging-port=%d", self._exe_path, self._cdp_port)
        subprocess.Popen(
            [self._exe_path, f"--remote-debugging-port={self._cdp_port}"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        logger.info("Waiting for CDP endpoint: %s ...", self._endpoint)
        wait_for_cdp_endpoint(self._endpoint, timeout=self._cdp_connect_timeout)
        self._connect_cdp()
        self._wait_for_main_ui()

        logger.info("App ready. URL: %s", self._page.url if self._page else "unknown")
        return self

    def connect(self) -> "ElectronApp":
        """连接到已用 --remote-debugging-port 启动的应用实例。

        Returns:
            self，支持链式调用。

        Raises:
            RuntimeError: CDP 端点不可达。
        """
        if not is_cdp_available(self._endpoint):
            raise RuntimeError(
                f"CDP 端点 {self._endpoint} 不可达。"
                f" 请先用 --remote-debugging-port={self._cdp_port} 启动应用。"
            )
        logger.info("Connecting to existing instance via CDP: %s", self._endpoint)
        self._connect_cdp()
        self._wait_for_main_ui()
        logger.info("Connected. URL: %s", self._page.url if self._page else "unknown")
        return self

    # ── Page 访问 ────────────────────────────────────────────────────────────

    @property
    def page(self) -> Page:
        """返回 Electron 主渲染页面。

        Raises:
            RuntimeError: 尚未调用 launch() 或 connect()。
        """
        if self._page is None:
            raise RuntimeError("请先调用 launch() 或 connect()。")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """返回 Playwright BrowserContext（用于捕获子窗口等）。

        Raises:
            RuntimeError: 尚未建立连接。
        """
        if self._context is None:
            raise RuntimeError("请先调用 launch() 或 connect()。")
        return self._context

    # ── 生命周期 ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """断开 Playwright 连接（不终止应用进程）。"""
        logger.debug("Closing Playwright connection...")
        for attr in ("_browser", "_pw"):
            obj = getattr(self, attr)
            if obj is not None:
                try:
                    obj.close() if attr == "_browser" else obj.stop()
                except Exception:
                    pass
                setattr(self, attr, None)
        self._context = None
        self._page = None

    def kill(self) -> None:
        """断开连接并强制终止应用进程。"""
        self.close()
        kill_processes(self._process_name)

    # ── 内部方法 ─────────────────────────────────────────────────────────────

    def _connect_cdp(self) -> None:
        """启动 Playwright 并通过 CDP 连接应用。"""
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.connect_over_cdp(self._endpoint)
        self._context = self._browser.contexts[0]
        self._page = self._context.pages[0]
        self._page.set_default_timeout(self._action_timeout_ms)
        logger.debug("CDP connected. Pages in context: %d", len(self._context.pages))

    def _wait_for_main_ui(self) -> None:
        """等待应用主 UI 加载完成。

        若指定了 ``loading_route``，等待 URL 不再包含该片段；
        否则仅等待固定稳定时间。
        """
        if self._page is None:
            return
        if self._loading_route:
            try:
                self._page.wait_for_url(
                    lambda url: self._loading_route not in url,  # type: ignore[operator]
                    timeout=self._app_load_timeout_ms,
                )
            except Exception:
                logger.warning("wait_for_main_ui timed out; continuing anyway.")
        self._page.wait_for_timeout(_POST_LOAD_SETTLE_MS)
