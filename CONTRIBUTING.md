# Contributing to winclient-auto

感谢你对 winclient-auto 的兴趣！本指南帮助你快速上手贡献。

## 贡献类型

### A) 新应用适配

在 `apps/` 下为新的 Windows 应用创建适配层是最有价值的贡献。

要求：

1. **适配器代码** — 在 `apps/<app_name>/` 下创建 `app.py`，继承 `ElectronApp`、`NativeApp` 或 `BrowserApp`
2. **Page Object** — 在 `pages/` 下继承 `BasePage` 实现页面操作
3. **常量定义** — 在 `constants.py` 中定义应用专属配置（EXE 路径、CDP 端口等）
4. **单元测试** — 在 `tests/<app_name>/` 下添加测试
5. **文档更新** — 更新 README.md 中的应用适配示例或添加新章节

### B) 框架新功能

改进框架核心（`winclient_auto/`）的功能，例如新增 CLI 命令、驱动支持、工具函数等。

- 先开 issue 讨论功能方案再动手
- 遵循现有代码风格和模式
- 新功能必须包含测试

### C) Bug 修复

- 在 PR 中引用相关 issue（如 `Fixes #123`）
- 包含能复现 bug 的测试
- 确保所有现有测试仍然通过

## 开发环境

```bash
# 克隆仓库
git clone <repo-url>
cd WinclientAuto

# 安装开发依赖
pip install -e ".[dev]"

# 安装 Playwright 浏览器
playwright install chromium

# 运行框架单元测试（不需要真实应用）
pytest tests/framework/ -v
```

### 环境要求

- Python 3.10+
- Windows 10/11（pywinauto 依赖）
- Playwright Chromium（Electron/Browser 测试需要）

## 代码风格

- 遵循 PEP 8 规范
- 使用类型注解（`disallow_untyped_defs = true`）
- 行宽 100 字符（ruff 配置）
- 所有 CLI 命令必须支持 `--json` 标志
- 使用 `ruff` 进行 lint：`ruff check .`
- 使用 `mypy` 进行类型检查：`mypy winclient_auto/`

## Commit 格式

使用 conventional commits 格式：

```
feat: 添加 BrowserApp 多标签页支持
fix: 修复 CDP 端口检测在高并发下的竞态问题
docs: 更新 README 卸载指令
test: 添加 NativeApp 单元测试
refactor: 重构 BasePage 截图逻辑
```

## 提交 PR

1. Fork 仓库并从 `master` 创建特性分支
2. 按上述规范完成修改
3. 确保所有测试通过：`pytest tests/framework/ -v`
4. 确保 lint 通过：`ruff check .`
5. 确保类型检查通过：`mypy winclient_auto/`
6. 推送分支并创建 Pull Request
7. 填写 PR 描述，说明修改内容和原因

## 问题反馈

有任何问题或建议，请开 issue 讨论。
