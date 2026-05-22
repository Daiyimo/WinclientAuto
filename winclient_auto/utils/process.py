"""进程管理工具。

封装 psutil 的进程操作，提供统一的进程查找、终止、状态检测接口。
所有操作均跨平台兼容（Windows / macOS / Linux）。

用法示例::

    from winclient_auto.utils.process import kill_processes, is_running

    kill_processes("MyApp")            # 终止所有名称含 "MyApp" 的进程
    is_running("Chrome")              # True / False
"""

from __future__ import annotations

import logging
import time

import psutil

logger = logging.getLogger(__name__)

# 终止进程后等待系统回收的秒数
_KILL_SETTLE_SECS: float = 1.0


def kill_processes(name_fragment: str, settle_secs: float = _KILL_SETTLE_SECS) -> int:
    """终止所有进程名包含 ``name_fragment`` 的进程。

    Args:
        name_fragment: 进程名称的子串，大小写敏感，如 "MyApp"、"chrome"。
        settle_secs: 终止后等待系统回收的秒数（默认 1s）。
                     若 ``settle_secs <= 0`` 则不等待。

    Returns:
        实际终止的进程数量。
    """
    killed = 0
    for proc in psutil.process_iter(["name"]):
        try:
            if name_fragment in proc.info["name"]:
                proc.terminate()
                killed += 1
                logger.debug("Terminated process: %s (pid=%d)", proc.info["name"], proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if killed and settle_secs > 0:
        logger.debug("Killed %d process(es), waiting %.1fs...", killed, settle_secs)
        time.sleep(settle_secs)

    return killed


def is_running(name_fragment: str) -> bool:
    """检查是否存在进程名包含 ``name_fragment`` 的进程。

    Args:
        name_fragment: 进程名称的子串，大小写敏感。

    Returns:
        True 表示至少存在一个匹配进程。
    """
    for proc in psutil.process_iter(["name"]):
        try:
            if name_fragment in proc.info["name"]:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def wait_for_process(
    name_fragment: str,
    timeout: float = 15.0,
    poll_interval: float = 0.5,
) -> bool:
    """等待指定进程启动，超时返回 False。

    Args:
        name_fragment: 进程名称的子串。
        timeout: 最长等待秒数（默认 15s）。
        poll_interval: 轮询间隔秒数（默认 0.5s）。

    Returns:
        True 表示进程在超时内启动，False 表示超时。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running(name_fragment):
            return True
        time.sleep(poll_interval)
    return False
