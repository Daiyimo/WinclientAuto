"""apps — 各 Windows 应用适配层。

在此目录下为每个目标应用创建子目录，包含：
- ``app.py``：继承 ElectronApp / NativeApp / BrowserApp 的适配器
- ``constants.py``：应用专属配置（EXE 路径、CDP 端口等）
- ``pages/``：继承 BasePage 的 Page Object
"""
