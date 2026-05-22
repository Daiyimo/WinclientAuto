"""BrowserApp — 基于 Playwright 的普通浏览器驱动。

适用于在普通 Chrome/Edge/Firefox 中运行的 Web 应用（非 Electron）。

用法示例::

    from winclient_auto.core.browser_app import BrowserApp

    app = BrowserApp(
        url="https://app.example.com/login",
        browser_type="chromium",   # chromium / firefox / webkit
        headless=False,
    )
    app.launch()
    page = app.page
    page.fill("input[name='username']", "admin")
    app.close()
"""

from __future__ import annotations

import logging

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from winclient_auto.core.base_app import WinClientApp

logger = logging.getLogger(__name__)

# 默认操作超时（毫秒）
_DEFAULT_ACTION_TIMEOUT_MS: int = 10_000

# 页面加载超时（毫秒）
_DEFAULT_LOAD_TIMEOUT_MS: int = 30_000


class BrowserApp(WinClientApp):
    """通过 Playwright 驱动普通浏览器应用。

    Args:
        url: 应用入口 URL；``connect()`` 时也会导航至此 URL。
        browser_type: 浏览器类型，``"chromium"``、``"firefox"`` 或 ``"webkit"``。
                      默认 ``"chromium"``。
        headless: 是否无头模式，默认 ``False``（有界面）。
        action_timeout_ms: 操作默认超时（毫秒），默认 10000。
        load_timeout_ms: 页面加载超时（毫秒），默认 30000。
        launch_args: 传给 Playwright launch 的额外参数字典。
    """

    def __init__(
        self,
        url: str,
        browser_type: str = "chromium",
        headless: bool = False,
        action_timeout_ms: int = _DEFAULT_ACTION_TIMEOUT_MS,
        load_timeout_ms: int = _DEFAULT_LOAD_TIMEOUT_MS,
        launch_args: dict | None = None,
    ) -> None:
        self._url = url
        self._browser_type = browser_type
        self._headless = headless
        self._action_timeout_ms = action_timeout_ms
        self._load_timeout_ms = load_timeout_ms
        self._launch_args: dict = launch_args or {}

        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ── 连接方式 ─────────────────────────────────────────────────────────────

    def launch(self) -> "BrowserApp":
        """启动浏览器并导航到目标 URL。

        Returns:
            self，支持链式调用。
        """
        logger.info("Launching %s browser (headless=%s)...", self._browser_type, self._headless)
        self._pw = sync_playwright().start()
        browser_launcher = getattr(self._pw, self._browser_type)
        self._browser = browser_launcher.launch(
            headless=self._headless,
            **self._launch_args,
        )
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._page.set_default_timeout(self._action_timeout_ms)

        logger.info("Navigating to: %s", self._url)
        self._page.goto(self._url, timeout=self._load_timeout_ms)
        return self

    def connect(self) -> "BrowserApp":
        """等同于 launch()（浏览器无"连接已有实例"语义，直接重新打开）。

        Returns:
            self，支持链式调用。
        """
        logger.warning("BrowserApp.connect() called; performing fresh launch instead.")
        return self.launch()

    # ── Page 访问 ────────────────────────────────────────────────────────────

    @property
    def page(self) -> Page:
        """返回当前浏览器页面。

        Raises:
            RuntimeError: 尚未调用 launch()。
        """
        if self._page is None:
            raise RuntimeError("请先调用 launch()。")
        return self._page

    # ── 生命周期 ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """关闭浏览器（不涉及外部进程）。"""
        logger.debug("Closing browser...")
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
