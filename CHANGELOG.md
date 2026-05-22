# Changelog

All notable changes to winclient-auto will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]

## [0.1.0] - 2026-05-22

### Added
- 框架核心：`WinClientApp` 抽象基类，统一 launch/connect/close/kill/page 接口
- `ElectronApp`：Playwright CDP 驱动的 Electron 客户端（参数化 exe 路径、进程名、CDP 端口、加载路由）
- `NativeApp`：pywinauto 驱动的 Win32 原生应用
- `BrowserApp`：标准 Playwright 浏览器驱动
- `BasePage`：通用页面操作基类（截图、Tab 切换、等待）
- `utils.process`：进程管理工具（kill_processes、is_running、wait_for_process）
- `utils.cdp`：CDP 端口就绪检测工具
- `utils.csv_loader`：通用 CSV 数据驱动加载器（参数化列名）
- `pytest_plugin.fixtures`：可复用的 pytest fixtures（winclient_app、winclient_page、inter_test_delay）
- `wca` CLI：双模式（子命令 + REPL），支持 `--json` 输出，涵盖 app/dom/native 三组命令
- `SKILL.md`：Agent 发现文档
- 框架单元测试：cdp、csv_loader、process 共 24 个测试用例
- `conftest.py`：通用 pytest hooks（Allure 失败截图、JUnit XML 格式化、环境信息写入）
- `apps/`：应用适配层包结构
- `pyproject.toml`：构建配置、pytest/ruff/mypy 工具链配置
- `CONTRIBUTING.md`：贡献指南
- `SECURITY.md`：安全策略
- `.github/`：Issue 模板、PR 模板、CODEOWNERS
