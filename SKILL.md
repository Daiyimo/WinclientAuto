---
name: "winclient-auto"
description: >-
  Windows 客户端自动化框架（wca CLI）。支持 Electron/CDP、Win32 原生（pywinauto）、
  普通浏览器（Playwright）三类应用的启动、连接、DOM 操作和原生控件操作。
  适合在 agent 中自动化测试 Windows 桌面客户端，所有命令支持 --json 输出。
install: "pip install winclient-auto"
---

# winclient-auto — Windows Client Auto

面向 agent 的 Windows 客户端自动化框架。

## 安装

```bash
pip install winclient-auto
playwright install chromium   # Electron/Browser 应用需要
```

## 快速开始

```bash
# 启动 Electron 应用（同时保存会话状态到 .wca_session.json）
wca app launch --exe "C:\Path\To\YourApp.exe" --process YourApp --type electron --cdp-port 9222

# 截图（JSON 输出，适合 agent 解析）
wca dom screenshot --output step1.png --json

# 点击元素
wca dom click --sel "button:has-text('开始')"

# 等待元素出现
wca dom wait --sel ".some-class" --state visible --timeout 15000

# 获取元素文本
wca dom get-text --sel ".some-class" --json

# 终止应用
wca app kill

# 交互式 REPL 模式（无子命令）
wca
```

## 命令参考

### app — 应用生命周期

| 命令 | 说明 |
|------|------|
| `wca app launch` | 启动应用并建立连接，保存会话状态 |
| `wca app connect` | 连接到已运行的应用（无需重启）|
| `wca app kill` | 终止应用进程并清除会话 |
| `wca app status` | 查看当前会话和 CDP 连接状态 |

**launch 参数：**
- `--exe <path>` 应用可执行文件路径（必填）
- `--process <name>` 进程名片段，用于 kill（必填）
- `--type electron|native|browser` 应用类型（默认 electron）
- `--cdp-port <port>` CDP 调试端口（默认 9222，Electron 专用）
- `--loading-route <fragment>` 加载路由片段，等待离开后认为加载完（如 `#/loading`）

### dom — DOM 操作（Electron / Browser）

| 命令 | 说明 |
|------|------|
| `wca dom screenshot` | 截取全页截图 |
| `wca dom click --sel <css>` | 点击 CSS 选择器匹配的元素 |
| `wca dom fill --sel <css> --text <value>` | 向输入框填入文本 |
| `wca dom get-text --sel <css>` | 获取元素文本内容 |
| `wca dom count --sel <css>` | 统计元素数量 |
| `wca dom wait --sel <css> [--state visible\|hidden]` | 等待元素达到指定状态 |
| `wca dom eval --js <script>` | 执行 JavaScript 并返回结果 |

### native — Win32 原生控件（pywinauto）

| 命令 | 说明 |
|------|------|
| `wca native list-windows` | 列出当前所有可见窗口 |
| `wca native click --window <title> --control <name>` | 点击控件 |
| `wca native type --window <title> --control <name> --text <text>` | 输入文本 |
| `wca native screenshot --window <title>` | 截取原生窗口截图 |

## JSON 输出格式

所有命令支持 `--json` 标志，输出格式：

```json
// 成功
{"status": "success", "message": "...", "data": {...}}

// 失败（同时以非零退出码退出）
{"status": "error", "message": "错误描述"}
```

## Python API

### 框架核心

```python
from winclient_auto.core.electron_app import ElectronApp
from winclient_auto.core.native_app import NativeApp
from winclient_auto.core.browser_app import BrowserApp
from winclient_auto.core.base_page import BasePage

# Electron 应用
app = ElectronApp(
    exe_path=r"C:\MyApp\app.exe",
    process_name="MyApp",
    cdp_port=9222,
    loading_route="#/loading",
)
app.launch()
page = app.page          # playwright.sync_api.Page
context = app.context    # playwright.sync_api.BrowserContext
app.close()

# Win32 原生应用
native = NativeApp(exe_path=r"C:\App.exe", process_name="App", backend="uia")
native.launch()
win_app = native.page    # pywinauto.Application

# 浏览器应用
browser = BrowserApp(url="https://example.com", headless=False)
browser.launch()
```

### Page Object 扩展

```python
from winclient_auto.core.base_page import BasePage

class MyAppPage(BasePage):
    # 选择器作为类常量，便于统一修改
    LOGIN_BTN_SEL = "button[data-testid='login']"
    TAB_SEL = ".app-tab"
    TAB_LOAD_TIMEOUT = {"Home": 5000, "Settings": 10000}

    def click_login(self) -> None:
        self._page.locator(self.LOGIN_BTN_SEL).click()

    def switch_to_tab(self, tab_name: str) -> None:
        self.click_tab(tab_name)
        self.wait_for_tab_loaded(tab_name)
```

### 数据驱动测试（CSV）

```python
from winclient_auto.utils.csv_loader import load_cases
import pytest

@pytest.mark.parametrize("name,expected", load_cases(
    Path("data/cases.csv"),
    columns=["name", "expected"],
    mark_filter="smoke",
))
def test_something(name: str, expected: str) -> None:
    ...
```

### pytest Fixtures 复用

```python
# tests/conftest.py（应用项目）
from winclient_auto.pytest_plugin.fixtures import make_winclient_fixtures

# 示例：自定义应用适配器
class MyApp(ElectronApp):
    pass

app, page = make_winclient_fixtures(lambda: MyApp(
    exe_path=r"C:\MyApp\app.exe",
    process_name="MyApp",
))
# 现在 app、page、inter_test_delay 可直接在测试中使用
```

## 会话持久化

`wca` 命令自动在当前目录创建 `.wca_session.json`，记录连接信息，
后续的 `dom`/`native` 命令无需每次指定连接参数：

```json
{
  "app_type": "electron",
  "exe_path": "C:\\Path\\To\\YourApp.exe",
  "process_name": "YourApp",
  "cdp_port": 9222
}
```

## 为 Agent 使用

1. 始终使用 `--json` 标志获取结构化输出
2. 检查 `status` 字段判断成功/失败（非零退出码也表示失败）
3. 使用 `wca app status --json` 验证连接状态再执行 DOM 操作
4. 截图保存路径在 `data.path` 字段中
5. 捕获子窗口（Electron 新窗口）需通过 Python API 使用 `context.expect_page()`
