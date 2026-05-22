"""CDP（Chrome DevTools Protocol）端口就绪检测工具。

Electron 应用以 ``--remote-debugging-port`` 启动后，CDP 端点会在
``http://localhost:<port>/json`` 开始响应。本模块提供轮询函数，
确保连接建立前 CDP 端点已就绪。

用法示例::

    from winclient_auto.utils.cdp import wait_for_cdp_endpoint

    wait_for_cdp_endpoint("http://localhost:9222", timeout=15)
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# CDP json 接口路径，返回当前所有可调试目标列表
_CDP_JSON_PATH: str = "/json"


def wait_for_cdp_endpoint(
    endpoint: str,
    timeout: int = 15,
    poll_interval: float = 0.5,
) -> None:
    """轮询直到 CDP 端点可达，或超时抛出 RuntimeError。

    Args:
        endpoint: CDP 根地址，如 ``"http://localhost:9222"``。
        timeout: 最长等待秒数（默认 15s）。
        poll_interval: 轮询间隔秒数（默认 0.5s）。

    Raises:
        RuntimeError: 超时仍未就绪。
    """
    url = endpoint.rstrip("/") + _CDP_JSON_PATH
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            logger.debug("CDP endpoint ready: %s", endpoint)
            return
        except Exception:
            time.sleep(poll_interval)

    raise RuntimeError(
        f"CDP 端点 {endpoint} 在 {timeout}s 内未响应。"
        " 请确认应用已使用 --remote-debugging-port 启动。"
    )


def is_cdp_available(endpoint: str, timeout: float = 1.0) -> bool:
    """快速检测 CDP 端点当前是否可达（不抛异常）。

    Args:
        endpoint: CDP 根地址。
        timeout: 单次请求超时秒数（默认 1s）。

    Returns:
        True 表示端点可达。
    """
    url = endpoint.rstrip("/") + _CDP_JSON_PATH
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False
