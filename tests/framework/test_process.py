"""单元测试：winclient_auto.utils.process。

覆盖 kill_processes、is_running、wait_for_process 的核心逻辑。
使用 mock 替代真实进程，测试不依赖任何外部进程。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from winclient_auto.utils.process import is_running, kill_processes, wait_for_process


# ── kill_processes ─────────────────────────────────────────────────────────────

class TestKillProcesses:
    def _make_proc(self, name: str, pid: int = 1) -> MagicMock:
        proc = MagicMock()
        proc.info = {"name": name}
        proc.pid = pid
        return proc

    def test_kills_matching_processes(self) -> None:
        procs = [
            self._make_proc("MyApp.exe", 100),
            self._make_proc("MyApp.exe", 101),
            self._make_proc("chrome.exe", 200),
        ]
        with patch("winclient_auto.utils.process.psutil.process_iter", return_value=procs):
            with patch("winclient_auto.utils.process.time.sleep"):
                count = kill_processes("MyApp", settle_secs=0.01)

        assert count == 2
        procs[0].terminate.assert_called_once()
        procs[1].terminate.assert_called_once()
        procs[2].terminate.assert_not_called()

    def test_returns_zero_when_no_match(self) -> None:
        procs = [self._make_proc("chrome.exe")]
        with patch("winclient_auto.utils.process.psutil.process_iter", return_value=procs):
            count = kill_processes("MyApp", settle_secs=0)

        assert count == 0

    def test_no_sleep_when_nothing_killed(self) -> None:
        procs = [self._make_proc("other.exe")]
        with patch("winclient_auto.utils.process.psutil.process_iter", return_value=procs):
            with patch("winclient_auto.utils.process.time.sleep") as mock_sleep:
                kill_processes("MyApp", settle_secs=1)

        mock_sleep.assert_not_called()

    def test_skips_no_such_process(self) -> None:
        import psutil  # noqa: PLC0415

        proc = self._make_proc("MyApp.exe")
        proc.terminate.side_effect = psutil.NoSuchProcess(pid=1)
        with patch("winclient_auto.utils.process.psutil.process_iter", return_value=[proc]):
            # 不应抛异常
            count = kill_processes("MyApp", settle_secs=0)
        # NoSuchProcess 发生在 terminate，计数仍为 0（terminate 抛出后未到 killed += 1）
        assert count == 0


# ── is_running ─────────────────────────────────────────────────────────────────

class TestIsRunning:
    def _make_proc(self, name: str) -> MagicMock:
        proc = MagicMock()
        proc.info = {"name": name}
        return proc

    def test_returns_true_when_process_exists(self) -> None:
        procs = [self._make_proc("MyApp.exe")]
        with patch("winclient_auto.utils.process.psutil.process_iter", return_value=procs):
            assert is_running("MyApp") is True

    def test_returns_false_when_not_found(self) -> None:
        procs = [self._make_proc("chrome.exe")]
        with patch("winclient_auto.utils.process.psutil.process_iter", return_value=procs):
            assert is_running("MyApp") is False

    def test_returns_false_for_empty_list(self) -> None:
        with patch("winclient_auto.utils.process.psutil.process_iter", return_value=[]):
            assert is_running("MyApp") is False


# ── wait_for_process ───────────────────────────────────────────────────────────

class TestWaitForProcess:
    def test_returns_true_when_process_starts_quickly(self) -> None:
        call_count = 0

        def fake_is_running(name: str) -> bool:
            nonlocal call_count
            call_count += 1
            return call_count >= 2  # 第2次调用才返回 True

        with patch("winclient_auto.utils.process.is_running", side_effect=fake_is_running):
            with patch("winclient_auto.utils.process.time.sleep"):
                result = wait_for_process("MyApp", timeout=5, poll_interval=0.01)

        assert result is True

    def test_returns_false_on_timeout(self) -> None:
        with patch("winclient_auto.utils.process.is_running", return_value=False):
            with patch("winclient_auto.utils.process.time.monotonic") as mock_time:
                # 模拟时间超过 timeout
                mock_time.side_effect = [0, 0.1, 10.0, 10.0]
                with patch("winclient_auto.utils.process.time.sleep"):
                    result = wait_for_process("MyApp", timeout=5, poll_interval=0.01)

        assert result is False
