# 完整平台体验验收：失败后能够继续

2026-10-27。在 `codex/full-platform-migration` 的 `5e978a5` 上继续，修复放在 `codex/platform-experience-check`。本轮遵循用户选择，先检查完整体验；保留灰紫聊天、模型选择、记忆、阅读器、资料库、米色学习笔记、工具和视频入口。没有新增治理算法或接入私人应用。

## 改了什么，在哪里验证

| 操作 | 修复前复现 | 现在看到什么算成功 |
|---|---|---|
| 聊天写一句话，点侧栏「导入历史记录」，再点「回到对话」，或刷新页面 | 未发送文字消失 | 文字恢复，并提示引用和附件需重新选择；不会自动发送 |
| 点发送，在提交响应尚未返回时连续再点 | 同一界面发出两次提交请求；服务器可能拒绝其中一次，但客户端未阻止 | 第一次提交期间按钮不可重复提交；拒绝后保留草稿，可再次操作 |
| 等待提交时继续写下一句 | 第一条提交成功后会清空新写的文字 | 只清除本次已提交且未再改动的文字，新输入仍留在输入框 |
| 书架打开 PDF/EPUB，在文字读取失败后展开「本轮可读原文」 | 一直显示读取中，旧书页仍可被重新带入 | 明确显示原文未加载、暂不带入旧页，点「重试读取原文」恢复当前片段 |
| 共读聊天里打开已有文档附件，在弹层点「附到聊天」 | 聊天区仍挂在已隐藏的阅读页，输入框不可见 | 返回正常聊天，输入框可见，文档版本标签在输入框旁 |
| 窄屏开启学习模式，收藏、评论、移入回收站、恢复、返回对话 | 核心流程本轮检查通过；截图发现操作按钮的三个点竖向折行 | 保留米色笔记与完整批注；操作按钮单行，恢复后评论仍在，返回时聚焦原消息 |

读取失败和提交延迟在自动验收中由本机测试拦截器注入；普通应用不会制造这些错误或展示模拟回复。用测试夹具展示的对话均带“合成演示，非模型生成”标记，正常启动不写入演示消息。

## 文字草稿的保存边界

文字草稿只保存在当前标签页的浏览器会话存储中，按本次服务实例隔离。可跨刷新和导入页往返恢复；同一实例内未发送的引用、附件、书页选择暂不保存，恢复时明确提示重新选择。关闭标签页、服务重启、换浏览器或换实例不保证恢复；不同实例不读取彼此草稿。草稿不写入聊天档案或记忆索引，不发送到供应商。清空输入或成功提交且没有新编辑时移除当前文字草稿。浏览器禁止会话存储时仍可聊天，但无法保证恢复。

本轮选择只保存文字，是为避免刷新后静默复用已失效的附件版本或书页。完整草稿（引用/附件/书页）若以后实现，需要逐项校验来源和当前状态，不能只恢复一个过期 ID。

## 验证证据

环境：Linux / Python 3.12.14；仓库独立 `.venv` 安装 requirements.txt，`pip check` 通过。五项固定应用依赖为 Pillow 12.3.0、pypdf 6.10.0、python-docx 1.2.0、cryptography 50.0.2、websockets 15.0.1；解析到的间接依赖为 cffi 2.1.1、lxml 6.1.3、pycparser 3.12、typing_extensions 4.16.0。未安装语义依赖或下载权重。

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tools/package.py verify
CONTINUITY_PYTHON="$PWD/.venv/bin/python" CONTINUITY_CHROMIUM=/usr/bin/chromium node tools/check_platform_browser.cjs
CONTINUITY_PYTHON="$PWD/.venv/bin/python" CONTINUITY_CHROMIUM=/usr/bin/chromium node tools/check_browser.cjs
CONTINUITY_PYTHON="$PWD/.venv/bin/python" CONTINUITY_CHROMIUM=/usr/bin/chromium node tools/check_platform_recovery.cjs
```

34 项离线测试通过。已有 Playwright 1.62.1 / Chromium 154.0.8037.57 通过完整平台和旧导入页流程。新恢复脚本最初复现四项失败，修复后七项检查通过：草稿往返、重复提交与拒绝、成功提交后的新输入保护、阅读失败/重试、共读附件返回聊天、390px 笔记实际操作、正常入口空实例。最后一项使用真正的 `python -m continuity`；未配置模型时保留输入、没有生成回复、聊天和费用记录为空。窄屏笔记按钮折行另按截图修复并检查尺寸。

浏览器脚本使用临时 profile，阻止外部页面请求，不申请摄像头或麦克风权限。新脚本中接受提交和任务结束的模拟仅用于界面状态检查，不作为真实供应商成功证据。截图仅含合成内容，放在 `.local/platform-recovery/`，不提交 Git。

这些结果不验证真实模型、现行价格、真实手机键盘/锁屏、语义召回质量、长期大库表现或新治理机制。14 个 governance-cases 仍未执行，不计入任何通过数。不会据此宣称私人应用费用下降。

## 实现与回退

- `app/static/app.js`：标签页文字草稿、提交等待互斥和提交后新输入保留。
- `app/static/reader.js`、`index.html`：清除过期书页状态、明确失败、原文重试。
- `app/static/library.js`：共读附件返回可见聊天。
- `app/static/study.js`、`study.css`：窄屏笔记操作按钮不折行。
- `tools/browser_fixture.py`：仅增加虚构附件，普通启动不使用它。
- `tools/check_platform_recovery.cjs`：新浏览器验收脚本。

无数据库迁移；回退该功能提交即可恢复迁入基线，原 profile 数据不需要迁移或删除。源代码来源哈希保留在 provenance-platform.json；当前字节由刷新后的 PACKAGE_MANIFEST.json 校验。新分支以完整迁入分支为基础审阅，不覆盖旧 main，也不自动合并迁入 PR。
