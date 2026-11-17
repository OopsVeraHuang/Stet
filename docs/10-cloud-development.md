# 本地与云端开发

2026-11-17：品牌更新为 Stet，保留 continuity 命令和 profile 路径。最新操作与原生导入边界见 `14-getting-started.md` / `15-getting-started.en.md`。本轮四个浏览器入口为 check_browser.cjs、check_platform_browser.cjs、check_platform_recovery.cjs、check_stet_browser.cjs；设置 `CONTINUITY_PYTHON` 指向已安装依赖的虚拟环境，必要时用 `CONTINUITY_CHROMIUM` 指向现有浏览器。

GitHub 保存工程，开发环境运行代码，应用服务器持续提供访问。上传 GitHub 不等于上线。每个环境有自己的 profile 和密钥，不能把 SQLite 或登录凭据提交共享。

## 当前仓库与云环境绑定

仓库地址为 [OopsVeraHuang/Stet](https://github.com/OopsVeraHuang/Stet)，Git 远端为 `https://github.com/OopsVeraHuang/Stet.git`，当前开发入口是 `main`。已有检出可以运行 `git remote set-url origin https://github.com/OopsVeraHuang/Stet.git` 后再 `git fetch origin`；这只更新远端地址，不改变本地资料或历史。

2026-11-17 检查发现，旧 Codex 云环境仍有按原仓库路径及早期提交固定的配置，不能把本地远端修复当成这些配置也已更新。请在 [Codex 环境设置](https://chatgpt.com/codex/settings/environments) 中重新选择当前仓库和 `main`，保留原有环境变量及权限。当前工具只能列出这些配置，浏览器编辑入口不可用，因此该项尚未代为修改。新的云端运行须再核对实际检出的提交。[官方环境说明](https://learn.chatgpt.com/docs/environments/cloud-environment)

## 应用安装

Python 3.11+，从仓库根目录安装 requirements.txt。推荐虚拟环境；Windows 用 .venv/Scripts/python，Linux/macOS 用 .venv/bin/python。

```text
python -m venv .venv
python -m pip install -r requirements.txt
python -X utf8 -m continuity --port 8780 --data-dir .local/my-profile
```

上面后两行的 python 请使用刚建立的虚拟环境解释器。默认只监听 127.0.0.1。浏览、导入、读书不请求模型；不填供应商密钥也能检查这些功能。当前平台不是纯标准库程序，Pillow 等应用依赖必须安装。没有配置云端公开访问，本地 URL 在云端属于那台机器。

## 免费本地语义检索（可选）

```text
python -m pip install -r requirements-semantic.txt
python tools/install_semantic.py
```

下载固定版本公共 ONNX 权重并逐文件核对 SHA-256，约百 MB 量级，本地存入被 Git 忽略的 .local/models。没有 embedding API 账单，不训练人格。首次下载需要网络，使用需 CPU/内存；不下载时保留词句召回，无付费回退。

PowerShell：
```powershell
$env:CONTINUITY_SEMANTIC_MODEL=(Resolve-Path .local/models/multilingual-minilm).Path
python -m continuity --data-dir .local/my-profile --open
```

Linux/macOS：
```sh
export CONTINUITY_SEMANTIC_MODEL="$PWD/.local/models/multilingual-minilm"
python -m continuity --data-dir .local/my-profile
```

## 分层检查

```text
python -m unittest discover -s tests -v
python tools/package.py verify
python tools/check_semantic.py
```

前两项不需权重或模型网络；第三项需要已安装语义依赖及上述环境变量，只使用合成中英俄文本，不能当成完整质量评测。

可选浏览器检查需要自行安装 Playwright 和 Chromium/Edge；不为普通使用者强制安装。环境变量 CONTINUITY_PYTHON 指向 Python、CONTINUITY_CHROMIUM 指向浏览器；完整平台检查默认 Windows Edge。

```text
node tools/check_browser.cjs
node tools/check_platform_browser.cjs
node tools/check_platform_recovery.cjs
```

第一项保留旧导入工作台回归，第二项检查完整平台，第三项检查草稿、提交、阅读失败恢复、共读附件与窄屏笔记；均创建临时合成 profile，禁止外部页面请求，不申请摄像头、不调用真实模型。截图只写 .local。完整测试服务器中的聊天清楚标为合成演示，不进入普通启动实例。

旧标准库切片仍可单独启动：
```text
python -c "from continuity.server import main; main()"
```

打包步骤见 docs/09-verification.md。没有 Git 的解压包可 verify；每次修改后必须刷新 staged 字节清单。不同操作系统须实际测试，不能把 Windows 通过写成 Linux 通过。
