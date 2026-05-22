"""单元测试：winclient_auto.utils.cdp。

覆盖 wait_for_cdp_endpoint 和 is_cdp_available 的核心逻辑。
使用 mock 替代真实 HTTP 请求。
"""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from winclient_auto.utils.cdp import is_cdp_available, wait_for_cdp_endpoint


# ── wait_for_cdp_endpoint ─────────────────────────────────────────────────────

class TestWaitForCdpEndpoint:
    def test_returns_immediately_when_endpoint_ready(self) -> None:
        with patch("winclient_auto.utils.cdp.urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            # 不应抛异常，应在第一次轮询就返回
            wait_for_cdp_endpoint("http://localhost:9222", timeout=5)

        mock_open.assert_called_once_with("http://localhost:9222/json", timeout=1)

    def test_raises_on_timeout(self) -> None:
        with patch("winclient_auto.utils.cdp.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            with patch("winclient_auto.utils.cdp.time.sleep"):
                with patch("winclient_auto.utils.cdp.time.monotonic") as mock_time:
                    mock_time.side_effect = [0, 0.5, 1.0, 20.0]
                    with pytest.raises(RuntimeError, match="CDP 端点.*未响应"):
                        wait_for_cdp_endpoint("http://localhost:9222", timeout=5)

    def test_retries_until_success(self) -> None:
        call_count = 0

        def fake_urlopen(*args, **kwargs) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.URLError("not ready yet")
            return MagicMock()

        with patch("winclient_auto.utils.cdp.urllib.request.urlopen", side_effect=fake_urlopen):
            with patch("winclient_auto.utils.cdp.time.sleep"):
                wait_for_cdp_endpoint("http://localhost:9222", timeout=15)

        assert call_count == 3

    def test_constructs_correct_json_url(self) -> None:
        with patch("winclient_auto.utils.cdp.urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            wait_for_cdp_endpoint("http://localhost:9999", timeout=5)

        args = mock_open.call_args[0]
        assert args[0] == "http://localhost:9999/json"

    def test_strips_trailing_slash(self) -> None:
        with patch("winclient_auto.utils.cdp.urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            wait_for_cdp_endpoint("http://localhost:9222/", timeout=5)

        args = mock_open.call_args[0]
        assert args[0] == "http://localhost:9222/json"


# ── is_cdp_available ──────────────────────────────────────────────────────────

class TestIsCdpAvailable:
    def test_returns_true_when_reachable(self) -> None:
        with patch("winclient_auto.utils.cdp.urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            assert is_cdp_available("http://localhost:9222") is True

    def test_returns_false_when_unreachable(self) -> None:
        with patch("winclient_auto.utils.cdp.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("refused")):
            assert is_cdp_available("http://localhost:9222") is False

    def test_returns_false_on_timeout(self) -> None:
        import socket  # noqa: PLC0415

        with patch("winclient_auto.utils.cdp.urllib.request.urlopen",
                   side_effect=socket.timeout()):
            assert is_cdp_available("http://localhost:9222") is False
