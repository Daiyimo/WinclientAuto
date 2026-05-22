"""NativeApp — 基于 pywinauto 的 Win32 原生应用驱动。

适用于传统 Win32 / WinForms / WPF 应用（非 Electron）。
通过 Windows UI Automation（UIA）或 Win32 控件树操作应用。

用法示例::

    from winclient_auto.core.native_app import NativeApp

    app = NativeApp(
        exe_path=r"C:\\Windows\\notepad.exe",
        process_name="notepad",
        backend="uia",          # 或 "win32"
    )
    app.launch()
    win_app = app.page         # pywinauto.Application 对象
    win_app.Notepad.Edit.type_keys("Hello")
    app.close()
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

from winclient_auto.core.base_app import WinClientApp
from winclient_auto.utils.process import kill_processes, wait_for_process

logger = logging.getLogger(__name__)

# 应用启动后等待主窗口出现的默认超时（秒）
_DEFAULT_START_TIMEOUT: int = 20

# 连接已运行应用时的默认超时（秒）
_DEFAULT_CONNECT_TIMEOUT: int = 10


class NativeApp(WinClientApp):
    """通过 pywinauto 驱动 Win32 原生应用。

    Args:
        exe_path: 应用可执行文件路径；``connect()`` 时可为空。
        process_name: 进程名称片段，用于 kill 和进程等待。
        backend: pywinauto 后端，``"uia"``（UIA，WPF/现代应用推荐）
                 或 ``"win32"``（Win32 经典控件推荐），默认 ``"uia"``。
        start_timeout: 启动后等待进程出现的超时（秒），默认 20。
        connect_timeout: 连接已有进程的超时（秒），默认 10。
        app_args: 启动应用时的额外命令行参数列表。
    """

    def __init__(
        self,
        exe_path: str = "",
        process_name: str = "",
        backend: str = "uia",
        start_timeout: int = _DEFAULT_START_TIMEOUT,
        connect_timeout: int = _DEFAULT_CONNECT_TIMEOUT,
        app_args: list[str] | None = None,
    ) -> None:
        self._exe_path = exe_path
        self._process_name = process_name
        self._backend = backend
        self._start_timeout = start_timeout
        self._connect_timeout = connect_timeout
        self._app_args: list[str] = app_args or []
        self._app: object | None = None  # pywinauto.Application

    # ── 连接方式 ─────────────────────────────────────────────────────────────

    def launch(self) -> "NativeApp":
        """启动应用并通过 pywinauto 连接。

        Returns:
            self，支持链式调用。

        Raises:
            ImportError: pywinauto 未安装。
            RuntimeError: 超时后进程未出现。
        """
        try:
            import pywinauto  # noqa: PLC0415
        except ImportError as e:
            raise ImportError("请安装 pywinauto：pip install pywinauto") from e

        if self._process_name:
            kill_processes(self._process_name)

        cmd = [self._exe_path, *self._app_args]
        logger.info("Launching native app: %s", " ".join(cmd))
        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        if self._process_name:
            started = wait_for_process(self._process_name, timeout=self._start_timeout)
            if not started:
                raise RuntimeError(
                    f"进程 '{self._process_name}' 在 {self._start_timeout}s 内未出现。"
                )
        else:
            time.sleep(2)

        self._app = pywinauto.Application(backend=self._backend).connect(
            path=self._exe_path,
            timeout=self._connect_timeout,
        )
        logger.info("NativeApp launched and connected.")
        return self

    def connect(self) -> "NativeApp":
        """连接到已运行的原生应用实例。

        Returns:
            self，支持链式调用。

        Raises:
            ImportError: pywinauto 未安装。
            RuntimeError: 未找到目标进程。
        """
        try:
            import pywinauto  # noqa: PLC0415
        except ImportError as e:
            raise ImportError("请安装 pywinauto：pip install pywinauto") from e

        if self._exe_path:
            self._app = pywinauto.Application(backend=self._backend).connect(
                path=self._exe_path,
                timeout=self._connect_timeout,
            )
        elif self._process_name:
            self._app = pywinauto.Application(backend=self._backend).connect(
                process=self._process_name,
                timeout=self._connect_timeout,
            )
        else:
            raise RuntimeError("connect() 需要提供 exe_path 或 process_name。")

        logger.info("NativeApp connected.")
        return self

    # ── Page 访问 ────────────────────────────────────────────────────────────

    @property
    def page(self) -> object:
        """返回 pywinauto.Application 对象。

        Raises:
            RuntimeError: 尚未调用 launch() 或 connect()。
        """
        if self._app is None:
            raise RuntimeError("请先调用 launch() 或 connect()。")
        return self._app

    # ── 生命周期 ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """释放 pywinauto 连接（不终止应用进程）。"""
        self._app = None
        logger.debug("NativeApp connection released.")

    def kill(self) -> None:
        """断开连接并终止应用进程。"""
        self.close()
        if self._process_name:
            kill_processes(self._process_name)
        elif self._exe_path:
            import os  # noqa: PLC0415
            kill_processes(os.path.basename(self._exe_path))
