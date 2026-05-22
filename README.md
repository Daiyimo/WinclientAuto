# winclient-auto

Windows 客户端自动化框架，支持 Electron/CDP、Win32 原生（pywinauto）、浏览器三类应用，
通过 `wca` CLI 供 agent 直接调用，所有命令支持 `--json` 输出。

## 特性

- **多客户端支持**：Electron（Playwright CDP）、Win32 原生（pywinauto）、Web 浏览器（Playwright）
- **Agent 友好**：`--json` 结构化输出 + 会话持久化，无需每次传连接参数
- **双模式 CLI**：子命令模式（脚本/agent）+ REPL 交互模式
- **Page Object 基类**：`BasePage` 提供 `current_url`、截图、Tab 切换、等待等通用操作
- **pytest 复用层**：`make_winclient_fixtures()` 工厂函数，一行生成 session 级 app fixture；内置通用 hooks（失败截图、JUnit XML 格式化、Allure 环境写入）
- **CSV 数据驱动**：`load_cases()` 支持参数化列名 + mark 过滤
- **Allure 报告**：失败用例自动截图附到报告，JUnit XML 自动格式化，无需额外配置

## 目录结构

```
WinclientAuto/
├── winclient_auto/              # 框架核心
│   ├── core/
│   │   ├── base_app.py          # WinClientApp 抽象基类
│   │   ├── electron_app.py      # Electron/CDP 驱动
│   │   ├── native_app.py        # pywinauto Win32 驱动
│   │   ├── browser_app.py       # Playwright 浏览器驱动
│   │   └── base_page.py         # Page Object 基类（含 current_url）
│   ├── utils/
│   │   ├── process.py           # psutil 进程工具
│   │   ├── cdp.py               # CDP 端口检测
│   │   └── csv_loader.py        # CSV 数据加载
│   ├── pytest_plugin/
│   │   └── fixtures.py          # 可复用 pytest fixtures
│   └── cli.py                   # wca CLI 入口
│
├── apps/                        # 各应用适配层（按需创建子目录）
│
├── tests/
│   ├── conftest.py              # 通用 pytest hooks（截图/XML/Allure）
│   └── framework/               # 框架单元测试（不依赖真实应用）
│
├── reports/                     # 测试报告输出目录
│   └── .gitkeep
│
├── .github/                     # GitHub 模板与配置
│   ├── ISSUE_TEMPLATE/          # Issue 模板（bug report / feature request）
│   ├── PULL_REQUEST_TEMPLATE.md # PR 模板
│   └── CODEOWNERS               # 默认 reviewer
│
├── LICENSE                      # MIT 许可证
├── CONTRIBUTING.md              # 贡献指南
├── SECURITY.md                  # 安全策略
├── CHANGELOG.md                 # 变更日志
├── SKILL.md                     # Agent 发现文档
├── README.md                    # 项目文档
└── pyproject.toml               # 构建配置与工具链
```

## 安装

```bash
pip install -e ".[dev]"
playwright install chromium
```

## 卸载

```bash
pip uninstall winclient-auto
```

## 更新

```bash
pip install --upgrade winclient-auto
```

开发模式下：

```bash
git pull
pip install -e ".[dev]"
```

## 快速开始

```bash
# 启动 Electron 应用
wca app launch --exe "D:\Apps\MyApp.exe" --process MyApp

# DOM 操作
wca dom click --sel "button:has-text('开始')"
wca dom screenshot --output step1.png
wca dom get-text --sel ".title" --json

# 应用状态
wca app status --json

# REPL 模式
wca
```

## 添加新应用适配

1. 在 `apps/` 下创建新目录：`apps/myapp/`
2. 创建 `app.py`，继承 `ElectronApp` 或 `NativeApp`
3. 创建 `constants.py`，定义应用专属常量
4. 创建 `pages/`，继承 `BasePage` 实现 Page Object

```python
# apps/myapp/app.py
from winclient_auto.core.electron_app import ElectronApp
from apps.myapp.constants import EXE_PATH, CDP_PORT

class MyApp(ElectronApp):
    def __init__(self) -> None:
        super().__init__(
            exe_path=EXE_PATH,
            process_name="MyApp",
            cdp_port=CDP_PORT,
            loading_route="#/loading",
        )
```

```python
# apps/myapp/pages/main_page.py
from winclient_auto.core.base_page import BasePage

class MainPage(BasePage):
    TAB_SEL = ".tab-item"
    TAB_LOAD_TIMEOUT = {"首页": 10_000, "详情": 15_000}

    BTN_SEL = "button.primary"

    def click_primary(self) -> None:
        self._page.locator(self.BTN_SEL).click()

    def assert_url_contains(self, fragment: str) -> None:
        assert fragment in self.current_url, f"URL 应包含 '{fragment}'，实际: {self.current_url}"
```

## 编写测试

```python
# tests/myapp/conftest.py
import pytest
from apps.myapp.app import MyApp
from apps.myapp.pages.main_page import MainPage
from winclient_auto.pytest_plugin.fixtures import make_winclient_fixtures

app, page = make_winclient_fixtures(lambda: MyApp())

@pytest.fixture
def main_page(page):
    return MainPage(page)
```

```python
# tests/myapp/test_basic.py
import pytest

@pytest.mark.smoke
def test_app_starts(main_page):
    assert "myapp" in main_page.current_url
```

## 运行测试

```bash
# 框架单元测试（不启动真实应用）
pytest tests/framework/ -v

# 冒烟测试（需真实应用）
pytest -m smoke -v

# 全量回归
pytest -m regression -v
```

## Allure 报告

```bash
# 生成 HTML 报告（需要 Allure CLI）
allure generate reports/allure-results -o reports/allure-report --clean

# 打开报告
allure open reports/allure-report
```

> **内置行为**（`tests/conftest.py` 自动生效，无需配置）：
> - 测试**失败时**自动截图，直接附加到 Allure 报告，不产生本地文件
> - 测试结束后格式化 JUnit XML，自动还原中文 Unicode 转义
> - 每次运行写入 `reports/allure-results/environment.properties`

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `WCA_TEST_DELAY` | 用例间隔秒数 | `3` |

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境搭建、代码风格和 PR 流程。

## 安全

发现安全漏洞请参阅 [SECURITY.md](SECURITY.md) 了解负责任的报告流程。
