"""BasePage — 通用 Page Object 基类。

提供所有页面对象共享的基础能力：截图、等待、Tab 切换。
应用特定的选择器和业务逻辑由子类定义；本类不包含任何业务代码。

用法示例::

    from winclient_auto.core.base_page import BasePage
    from playwright.sync_api import Page

    class LoginPage(BasePage):
        USERNAME_SEL = "input[name='username']"
        PASSWORD_SEL = "input[name='password']"

        def login(self, username: str, password: str) -> None:
            self._page.fill(self.USERNAME_SEL, username)
            self._page.fill(self.PASSWORD_SEL, password)
            self._page.click("button[type='submit']")
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Locator, Page


class BasePage:
    """Page Object 通用基类。

    Args:
        page: Playwright Page 对象。
        screenshot_dir: 截图保存目录；默认为 ``{cwd}/screenshots``。
    """

    # ── Tab 通用配置（子类按需覆盖）──────────────────────────────────────────

    # Tab 元素的 CSS 选择器
    TAB_SEL: str = ""

    # Tab 切换后额外等待渲染稳定的毫秒数
    TAB_STABLE_WAIT_MS: int = 2000

    # Tab 名称 → 最长加载超时（毫秒），子类按实际情况覆盖
    TAB_LOAD_TIMEOUT: dict[str, int] = {}

    def __init__(self, page: Page, screenshot_dir: Path | None = None) -> None:
        self._page = page
        self._screenshot_dir: Path = (
            screenshot_dir if screenshot_dir is not None else Path.cwd() / "screenshots"
        )

    # ── 当前 URL ──────────────────────────────────────────────────────────────

    @property
    def current_url(self) -> str:
        """返回当前页面的 URL 字符串。

        Returns:
            当前页面 URL。
        """
        return self._page.url

    # ── 截图 ──────────────────────────────────────────────────────────────────

    def screenshot(self, name: str, output_dir: Path | None = None) -> Path:
        """保存全页截图。

        Args:
            name: 文件名（不含扩展名），如 ``"step1_login"``。
            output_dir: 输出目录；若为 ``None`` 则使用初始化时指定的目录。

        Returns:
            截图文件的 Path 对象。
        """
        save_dir = output_dir if output_dir is not None else self._screenshot_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        path = save_dir / f"{name}.png"
        self._page.screenshot(path=str(path))
        return path

    # ── 等待 ──────────────────────────────────────────────────────────────────

    def wait_ms(self, ms: int) -> None:
        """等待指定毫秒数（让渲染稳定）。

        Args:
            ms: 等待时间（毫秒）。
        """
        self._page.wait_for_timeout(ms)

    # ── Tab 操作 ──────────────────────────────────────────────────────────────

    def _content_tab(self, tab_text: str) -> Locator:
        """返回内容区 Tab 的 Locator。

        当页面存在多个同名 Tab 时（如顶栏 + 内容区），用 ``.last`` 选取内容区。

        Args:
            tab_text: Tab 标签文本。

        Returns:
            内容区 Tab Locator。

        Raises:
            ValueError: :attr:`TAB_SEL` 未在子类中设置。
        """
        if not self.TAB_SEL:
            raise ValueError(
                f"{self.__class__.__name__} 需要设置 TAB_SEL 才能使用 Tab 操作。"
            )
        return self._page.locator(self.TAB_SEL, has_text=tab_text).last

    def click_tab(self, tab_text: str) -> None:
        """点击指定内容 Tab。

        Args:
            tab_text: Tab 标签文本。
        """
        self._content_tab(tab_text).click()

    def wait_for_tab_loaded(self, tab_text: str, default_timeout_ms: int = 10_000) -> None:
        """等待指定 Tab 激活并渲染稳定。

        等待策略：
          1. Tab 进入 active 状态（最长 :attr:`TAB_LOAD_TIMEOUT` 中对应值）
          2. 额外等待 :attr:`TAB_STABLE_WAIT_MS` 确保渲染完成

        Args:
            tab_text: Tab 标签文本。
            default_timeout_ms: TAB_LOAD_TIMEOUT 未包含该 Tab 时的默认超时。
        """
        timeout = self.TAB_LOAD_TIMEOUT.get(tab_text, default_timeout_ms)
        active_locator = self._page.locator(
            f"{self.TAB_SEL}.active", has_text=tab_text
        ).last
        active_locator.wait_for(state="visible", timeout=timeout)
        self._page.wait_for_timeout(self.TAB_STABLE_WAIT_MS)

    def is_tab_active(self, tab_text: str) -> bool:
        """检查指定 Tab 是否处于 active 状态。

        Args:
            tab_text: Tab 标签文本。

        Returns:
            True 表示 Tab 已激活。
        """
        return (
            self._page.locator(f"{self.TAB_SEL}.active", has_text=tab_text).last.count() > 0
        )
