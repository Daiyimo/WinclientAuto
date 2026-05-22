"""wca — Windows Client Auto CLI。

按 CLI-Anything 模式实现的双模式 CLI：
- 子命令模式：``wca app launch --exe ...``（适合脚本/agent 调用）
- REPL 模式：``wca``（无子命令时进入交互式会话）

所有命令支持 ``--json`` 标志，输出结构化 JSON，便于 agent 解析。

会话状态存储在当前目录的 ``.wca_session.json``，支持跨命令持久化。

用法示例::

    # 启动 Electron 应用
    wca app launch --exe "D:\\Apps\\MyApp.exe" --process MyApp --type electron

    # 截图（JSON 输出）
    wca dom screenshot --output step1.png --json

    # 点击元素
    wca dom click --sel "button:has-text('开始')"

    # REPL 交互模式
    wca
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from winclient_auto.utils.cdp import is_cdp_available

logger = logging.getLogger(__name__)

# 会话状态文件（per-directory）
_SESSION_FILE: str = ".wca_session.json"

# ── 全局状态 ──────────────────────────────────────────────────────────────────

_json_output: bool = False


# ── 输出工具 ──────────────────────────────────────────────────────────────────

def _out(data: dict[str, Any]) -> None:
    """统一输出：--json 时输出 JSON，否则输出人类可读格式。"""
    if _json_output:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        status = data.get("status", "")
        message = data.get("message", "")
        result_data = data.get("data", {})

        if status == "success":
            if message:
                click.secho(f"✓ {message}", fg="green")
            if result_data:
                _print_dict(result_data)
        elif status == "error":
            click.secho(f"✗ {message}", fg="red", err=True)
        else:
            if message:
                click.echo(message)
            if result_data:
                _print_dict(result_data)


def _print_dict(d: dict[str, Any], indent: int = 0) -> None:
    """递归打印字典（人类可读）。"""
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    click.echo(f"{prefix}  [{i}]:")
                    _print_dict(item, indent + 2)
                else:
                    click.echo(f"{prefix}  [{i}]: {item}")
        else:
            click.echo(f"{prefix}{k}: {v}")


def _err(message: str) -> None:
    """输出错误并以非零退出码退出。"""
    _out({"status": "error", "message": message})
    sys.exit(1)


# ── 会话管理 ──────────────────────────────────────────────────────────────────

def _load_session() -> dict[str, Any]:
    """从 .wca_session.json 加载连接状态。"""
    path = Path(_SESSION_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("会话文件损坏，已忽略: %s", exc)
    return {}


def _save_session(data: dict[str, Any]) -> None:
    """保存连接状态到 .wca_session.json。"""
    path = Path(_SESSION_FILE)
    data["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _clear_session() -> None:
    """删除会话状态文件。"""
    path = Path(_SESSION_FILE)
    if path.exists():
        path.unlink()


def _get_playwright_page(
    session: dict[str, Any],
) -> tuple[Any, Any, Any]:
    """根据会话信息获取 Playwright Page 对象（Electron/Browser）。

    Returns:
        ``(playwright, browser, page)`` 三元组，调用方需在 finally 中关闭。

    Raises:
        SystemExit: 会话不存在或连接失败。
    """
    app_type = session.get("app_type", "electron")
    if app_type == "electron":
        from winclient_auto.core.electron_app import ElectronApp  # noqa: PLC0415

        cdp_port = session.get("cdp_port", 9222)
        endpoint = f"http://localhost:{cdp_port}"
        if not is_cdp_available(endpoint):
            _err(f"CDP 端点 {endpoint} 不可达，应用可能已退出。运行 'wca app status' 查看状态。")

        from playwright.sync_api import sync_playwright  # noqa: PLC0415

        pw = sync_playwright().start()
        try:
            browser = pw.chromium.connect_over_cdp(endpoint)
            page = browser.contexts[0].pages[0]
            return pw, browser, page
        except Exception:
            pw.stop()
            raise
    elif app_type == "browser":
        _err("browser 类型应用请直接通过 Python API 操作。")
    else:
        _err(f"不支持的 app_type '{app_type}' 进行 DOM 操作。")


# ── CLI 主命令 ────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--json", "use_json", is_flag=True, default=False, help="以 JSON 格式输出结果")
@click.version_option(package_name="winclient-auto")
@click.pass_context
def main(ctx: click.Context, use_json: bool) -> None:
    """wca — Windows Client Auto：面向 agent 的 Windows 客户端自动化框架。

    \b
    子命令模式：wca app launch --exe "C:\\App.exe" --process App
    交互模式：  wca（无子命令时进入 REPL）
    JSON 输出： wca --json app status
    """
    global _json_output
    _json_output = use_json
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if ctx.invoked_subcommand is None:
        _run_repl()


# ── app 命令组 ────────────────────────────────────────────────────────────────

@main.group()
def app() -> None:
    """应用生命周期管理：launch / connect / kill / status。"""


@app.command("launch")
@click.option("--exe", required=True, help="应用可执行文件路径")
@click.option("--process", "process_name", required=True, help="进程名称片段（用于 kill）")
@click.option("--type", "app_type", default="electron",
              type=click.Choice(["electron", "native", "browser"]), show_default=True,
              help="应用类型")
@click.option("--cdp-port", default=9222, show_default=True, help="CDP 调试端口（Electron 专用）")
@click.option("--loading-route", default=None, help="加载路由片段（如 '#/loading'，Electron 专用）")
@click.option("--url", default=None, help="入口 URL（browser 类型专用）")
def app_launch(
    exe: str,
    process_name: str,
    app_type: str,
    cdp_port: int,
    loading_route: str | None,
    url: str | None,
) -> None:
    """启动应用并建立连接。"""
    try:
        if app_type == "electron":
            from winclient_auto.core.electron_app import ElectronApp  # noqa: PLC0415

            inst = ElectronApp(
                exe_path=exe,
                process_name=process_name,
                cdp_port=cdp_port,
                loading_route=loading_route,
            )
            inst.launch()
            _save_session({
                "app_type": app_type,
                "exe_path": exe,
                "process_name": process_name,
                "cdp_port": cdp_port,
                "loading_route": loading_route,
            })
            inst.close()  # 关闭 Playwright 连接，保留 CDP（进程继续运行）

        elif app_type == "native":
            from winclient_auto.core.native_app import NativeApp  # noqa: PLC0415

            inst_n = NativeApp(exe_path=exe, process_name=process_name)
            inst_n.launch()
            _save_session({
                "app_type": app_type,
                "exe_path": exe,
                "process_name": process_name,
            })
            inst_n.close()

        elif app_type == "browser":
            if not url:
                _err("browser 类型需要 --url 参数。")
            from winclient_auto.core.browser_app import BrowserApp  # noqa: PLC0415

            inst_b = BrowserApp(url=url)  # type: ignore[arg-type]
            inst_b.launch()
            _save_session({
                "app_type": app_type,
                "url": url,
            })
            # browser 应用保留打开状态，不 close

        _out({"status": "success", "message": f"{process_name} 启动成功", "data": {"app_type": app_type}})

    except Exception as exc:
        _err(str(exc))


@app.command("connect")
@click.option("--cdp-port", default=None, type=int, help="CDP 端口（覆盖会话中的值）")
def app_connect(cdp_port: int | None) -> None:
    """连接到已运行的应用实例。"""
    session = _load_session()
    if not session:
        _err("无会话状态，请先运行 'wca app launch'。")

    app_type = session.get("app_type", "electron")
    port = cdp_port or session.get("cdp_port", 9222)

    try:
        if app_type == "electron":
            from winclient_auto.core.electron_app import ElectronApp  # noqa: PLC0415

            inst = ElectronApp(
                exe_path=session.get("exe_path", ""),
                process_name=session.get("process_name", ""),
                cdp_port=port,
            )
            inst.connect()
            _save_session({**session, "cdp_port": port})
            inst.close()
            _out({"status": "success", "message": "已连接", "data": {"cdp_port": port}})
        elif app_type == "native":
            _err("native 类型不支持 connect 命令，请直接使用 'wca native' 子命令操作。")
        elif app_type == "browser":
            _err("browser 类型不支持 connect 命令，请通过 Python API 操作。")
        else:
            _err(f"不支持的 app_type '{app_type}'。")

    except Exception as exc:
        _err(str(exc))


@app.command("kill")
@click.option("--process", "process_name", default=None, help="进程名称（覆盖会话中的值）")
def app_kill(process_name: str | None) -> None:
    """终止应用进程。"""
    session = _load_session()
    target = process_name or session.get("process_name", "")
    if not target:
        _err("未找到进程名，请用 --process 指定或先运行 'wca app launch'。")

    from winclient_auto.utils.process import kill_processes  # noqa: PLC0415

    killed = kill_processes(target)
    _clear_session()
    _out({
        "status": "success",
        "message": f"已终止 {killed} 个 '{target}' 进程",
        "data": {"process_name": target, "killed_count": killed},
    })


@app.command("status")
def app_status() -> None:
    """查看当前会话和应用连接状态。"""
    session = _load_session()
    if not session:
        _out({"status": "success", "message": "无活跃会话", "data": {"connected": False}})
        return

    app_type = session.get("app_type", "electron")
    extra: dict[str, Any] = {}

    if app_type == "electron":
        port = session.get("cdp_port", 9222)
        endpoint = f"http://localhost:{port}"
        cdp_ok = is_cdp_available(endpoint)
        extra = {"cdp_port": port, "cdp_available": cdp_ok}

    from winclient_auto.utils.process import is_running  # noqa: PLC0415

    process_name = session.get("process_name", "")
    running = is_running(process_name) if process_name else None

    _out({
        "status": "success",
        "data": {
            "app_type": app_type,
            "process_name": process_name,
            "process_running": running,
            "exe_path": session.get("exe_path", ""),
            **extra,
        },
    })


# ── dom 命令组 ────────────────────────────────────────────────────────────────

@main.group()
def dom() -> None:
    """DOM 操作（适用于 Electron / Browser 应用）。"""


@dom.command("screenshot")
@click.option("--output", "-o", default=None, help="截图保存路径（默认：screenshots/wca_<时间戳>.png）")
def dom_screenshot(output: str | None) -> None:
    """截取当前页面截图。"""
    session = _load_session()
    if not session:
        _err("无会话，请先运行 'wca app launch'。")

    pw, browser, page = _get_playwright_page(session)
    try:
        if output is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path("screenshots") / f"wca_{ts}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            output = str(out_path)
        page.screenshot(path=output)
        _out({"status": "success", "message": f"截图已保存: {output}", "data": {"path": output}})
    except Exception as exc:
        _err(str(exc))
    finally:
        browser.close()
        pw.stop()


@dom.command("click")
@click.option("--sel", required=True, help="CSS 选择器")
@click.option("--timeout", default=10000, show_default=True, help="超时毫秒数")
def dom_click(sel: str, timeout: int) -> None:
    """点击 CSS 选择器匹配的元素。"""
    session = _load_session()
    if not session:
        _err("无会话，请先运行 'wca app launch'。")

    pw, browser, page = _get_playwright_page(session)
    try:
        page.locator(sel).click(timeout=timeout)
        _out({"status": "success", "message": f"已点击: {sel}", "data": {"selector": sel}})
    except Exception as exc:
        _err(str(exc))
    finally:
        browser.close()
        pw.stop()


@dom.command("fill")
@click.option("--sel", required=True, help="CSS 选择器")
@click.option("--text", required=True, help="要输入的文本")
@click.option("--timeout", default=10000, show_default=True, help="超时毫秒数")
def dom_fill(sel: str, text: str, timeout: int) -> None:
    """在输入框中填入文本。"""
    session = _load_session()
    if not session:
        _err("无会话，请先运行 'wca app launch'。")

    pw, browser, page = _get_playwright_page(session)
    try:
        page.locator(sel).fill(text, timeout=timeout)
        _out({"status": "success", "message": f"已填入文本: {sel}", "data": {"selector": sel, "text": text}})
    except Exception as exc:
        _err(str(exc))
    finally:
        browser.close()
        pw.stop()


@dom.command("get-text")
@click.option("--sel", required=True, help="CSS 选择器")
@click.option("--timeout", default=10000, show_default=True, help="超时毫秒数")
def dom_get_text(sel: str, timeout: int) -> None:
    """获取元素的文本内容。"""
    session = _load_session()
    if not session:
        _err("无会话，请先运行 'wca app launch'。")

    pw, browser, page = _get_playwright_page(session)
    try:
        text = page.locator(sel).first.inner_text(timeout=timeout)
        _out({"status": "success", "data": {"selector": sel, "text": text}})
    except Exception as exc:
        _err(str(exc))
    finally:
        browser.close()
        pw.stop()


@dom.command("count")
@click.option("--sel", required=True, help="CSS 选择器")
def dom_count(sel: str) -> None:
    """统计 CSS 选择器匹配到的元素数量。"""
    session = _load_session()
    if not session:
        _err("无会话，请先运行 'wca app launch'。")

    pw, browser, page = _get_playwright_page(session)
    try:
        count = page.locator(sel).count()
        _out({"status": "success", "data": {"selector": sel, "count": count}})
    except Exception as exc:
        _err(str(exc))
    finally:
        browser.close()
        pw.stop()


@dom.command("wait")
@click.option("--sel", required=True, help="CSS 选择器")
@click.option("--state", default="visible",
              type=click.Choice(["visible", "hidden", "attached", "detached"]),
              show_default=True, help="等待的目标状态")
@click.option("--timeout", default=10000, show_default=True, help="超时毫秒数")
def dom_wait(sel: str, state: str, timeout: int) -> None:
    """等待元素达到指定状态。"""
    session = _load_session()
    if not session:
        _err("无会话，请先运行 'wca app launch'。")

    pw, browser, page = _get_playwright_page(session)
    try:
        page.locator(sel).first.wait_for(state=state, timeout=timeout)  # type: ignore[arg-type]
        _out({"status": "success", "message": f"元素已{state}: {sel}", "data": {"selector": sel, "state": state}})
    except Exception as exc:
        _err(str(exc))
    finally:
        browser.close()
        pw.stop()


@dom.command("eval")
@click.option("--js", required=True, help="JavaScript 表达式")
def dom_eval(js: str) -> None:
    """在页面上下文中执行 JavaScript 并返回结果。"""
    session = _load_session()
    if not session:
        _err("无会话，请先运行 'wca app launch'。")

    pw, browser, page = _get_playwright_page(session)
    try:
        result = page.evaluate(js)
        _out({"status": "success", "data": {"result": result}})
    except Exception as exc:
        _err(str(exc))
    finally:
        browser.close()
        pw.stop()


# ── native 命令组 ─────────────────────────────────────────────────────────────

@main.group()
def native() -> None:
    """Win32 原生控件操作（pywinauto）。"""


@native.command("list-windows")
@click.option("--process", "process_name", default=None, help="按进程名过滤（可选）")
def native_list_windows(process_name: str | None) -> None:
    """列出可见的顶层窗口。"""
    try:
        from pywinauto import Desktop  # noqa: PLC0415

        desktop = Desktop(backend="uia")
        windows = []
        for win in desktop.windows():
            try:
                title = win.window_text()
                pid = win.process_id()
                if process_name:
                    import psutil  # noqa: PLC0415

                    try:
                        p = psutil.Process(pid)
                        if process_name.lower() not in p.name().lower():
                            continue
                    except psutil.NoSuchProcess:
                        continue
                windows.append({"title": title, "pid": pid})
            except Exception:
                pass

        _out({"status": "success", "data": {"windows": windows, "count": len(windows)}})

    except ImportError:
        _err("pywinauto 未安装，请运行: pip install pywinauto")
    except Exception as exc:
        _err(str(exc))


@native.command("click")
@click.option("--window", required=True, help="窗口标题（支持部分匹配）")
@click.option("--control", required=True, help="控件名称或 automation_id")
def native_click(window: str, control: str) -> None:
    """点击原生 Win32 控件。"""
    try:
        import pywinauto  # noqa: PLC0415

        app = pywinauto.Application(backend="uia").connect(title_re=f".*{re.escape(window)}.*")
        win = app.top_window()
        win[control].click_input()
        _out({"status": "success", "message": f"已点击控件: {control}", "data": {"window": window, "control": control}})

    except ImportError:
        _err("pywinauto 未安装，请运行: pip install pywinauto")
    except Exception as exc:
        _err(str(exc))


@native.command("type")
@click.option("--window", required=True, help="窗口标题")
@click.option("--control", required=True, help="控件名称或 automation_id")
@click.option("--text", required=True, help="要输入的文本")
def native_type(window: str, control: str, text: str) -> None:
    """向原生控件输入文本。"""
    try:
        import pywinauto  # noqa: PLC0415

        app = pywinauto.Application(backend="uia").connect(title_re=f".*{re.escape(window)}.*")
        win = app.top_window()
        win[control].type_keys(text, with_spaces=True)
        _out({"status": "success", "message": f"已输入文本到: {control}", "data": {"window": window, "control": control}})

    except ImportError:
        _err("pywinauto 未安装，请运行: pip install pywinauto")
    except Exception as exc:
        _err(str(exc))


@native.command("screenshot")
@click.option("--window", required=True, help="窗口标题")
@click.option("--output", "-o", default=None, help="截图保存路径")
def native_screenshot(window: str, output: str | None) -> None:
    """截取指定原生窗口的截图。"""
    try:
        import pywinauto  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        app = pywinauto.Application(backend="uia").connect(title_re=f".*{re.escape(window)}.*")
        win = app.top_window()
        img = win.capture_as_image()

        if output is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = Path("screenshots") / f"native_{ts}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            output = str(out_path)

        img.save(output)
        _out({"status": "success", "message": f"截图已保存: {output}", "data": {"path": output}})

    except ImportError as e:
        _err(f"依赖未安装: {e}。请运行: pip install pywinauto Pillow")
    except Exception as exc:
        _err(str(exc))


# ── REPL 模式 ─────────────────────────────────────────────────────────────────

def _run_repl() -> None:
    """进入交互式 REPL 会话。"""
    import shlex  # noqa: PLC0415

    click.secho("┌──────────────────────────────────────────┐", fg="cyan")
    click.secho("│  wca — Windows Client Auto  REPL 模式    │", fg="cyan")
    click.secho("│  输入 'help' 查看命令，'exit' 退出         │", fg="cyan")
    click.secho("└──────────────────────────────────────────┘", fg="cyan")

    session = _load_session()
    if session:
        app_type = session.get("app_type", "unknown")
        process = session.get("process_name", "")
        click.secho(f"  当前会话：{app_type} / {process}", fg="yellow")
    else:
        click.secho("  无活跃会话。使用 'app launch' 启动应用。", fg="yellow")

    click.echo()

    while True:
        try:
            prompt = click.style("wca ❯ ", fg="cyan", bold=True)
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\n再见！")
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit", "q"):
            click.echo("再见！")
            break
        if line.lower() == "help":
            click.echo("""
可用命令组：
  app launch   -- 启动应用并建立连接
  app connect  -- 连接到已运行的应用
  app kill     -- 终止应用进程
  app status   -- 查看会话状态
  dom screenshot -- 截取页面截图
  dom click    -- 点击元素
  dom fill     -- 填入文本
  dom get-text -- 获取元素文本
  dom count    -- 统计元素数量
  dom wait     -- 等待元素状态
  dom eval     -- 执行 JavaScript
  native list-windows -- 列出可见窗口
  native click -- 点击原生控件
  native type  -- 向原生控件输入文本
  native screenshot -- 截取原生窗口

选项：--json 以 JSON 格式输出
退出：exit / quit / q / Ctrl+D
""")
            continue

        # 将输入拼成命令行参数传给 Click
        try:
            args = shlex.split(line)
        except ValueError as e:
            click.secho(f"解析错误: {e}", fg="red")
            continue

        try:
            # standalone_mode=False 不调用 sys.exit
            main.main(args=args, standalone_mode=False)
        except SystemExit:
            pass
        except Exception as exc:
            click.secho(f"错误 [{type(exc).__name__}]: {exc}", fg="red")
