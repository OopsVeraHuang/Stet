# Stet 双语预览版：操作与验收

2026-11-17。保留完整平台和灰紫聊天界面，学习模式仍为米色纸张。工作名从 Continuity 改为 Stet；兼容旧命令与资料路径。私人应用及数据未修改。

## 可以直接点什么

| 用户需求 | 现在怎么操作 | 证明范围 |
|---|---|---|
| 中英双语 | 侧栏 Language / 语言 → English 或简体中文 | 标签与说明切换并记住选择，不翻译记录 |
| 设置整理 | 连接与预算 → 模型与连接 / 回答与记忆 / 伙伴与偏好 / 联网工具 / 费用与预算 | 原表单仍向同一后端保存；分类不复制密钥 |
| 笔记检索 | 开启学习模式 → 搜索摘录或评论 | 本地 Unicode 字面匹配；不是新训练的语义模型 |
| 原生聊天导入 | 导入历史记录 → 选择 JSON/ZIP → 看预览与遗漏 → 确认 | 支持列明的 ChatGPT / Claude / Gemini / AI Studio 文字结构；未知字段不猜测 |
| 视频 | 侧栏 Video · Beta / 视频 · Beta | 测试状态可见；本轮没有真实通话验收 |
| 工作室 | 主导航暂时隐藏 | 尚未作为试用功能开放；不代表已完成维修代理 |
| 使用说明 | 侧栏使用指南 / Getting started | 简版引导 + 中英 Markdown 手册下载 |

导入数据和学习笔记仍通过现有共同记忆入口检索。原件、来源、分支和角色分开保存；语言切换不会重新写入档案。原始 ZIP 作为原件保留，但只解析一个可识别的会话 JSON，不解压附件。导入前最多 32 MiB，展开后最多 20,000 条；预览显示前 200 条，验证和计数覆盖全部。详见 [中文手册](14-getting-started.md) / [English guide](15-getting-started.en.md)。

## 本轮实际验证

Windows / Python 3.12.14，已有 Playwright 与无头 Edge；全部使用新建的临时资料目录、合成记录、模拟供应商响应。没有付费调用、真实账号登录、设备授权、训练或上传私人档案。

- `python -X utf8 -m unittest discover -s tests -v`：**41 项通过**。包括 6 项新增原生导入检查及笔记搜索检查，覆盖 ChatGPT 分支、Claude 文字块、Takeout 不虚构回复、AI Studio、ZIP 原件/路径边界、坏结构拒绝，以及评论搜索/大小写/分页/回收站。
- `node tools/check_browser.cjs`：原工作台导入、出处、字面搜索、删除、窄屏回归通过。
- `node tools/check_platform_browser.cjs`：完整聊天 Markdown、阅读器实际 PDF/EPUB 渲染、笔记、独立设置、导入后共同召回和视频未授权拒绝通过。
- `node tools/check_platform_recovery.cjs`：7 项草稿、重复提交、阅读失败恢复、窄屏笔记和空资料目录检查通过。Windows 在切换页面取消未完成 HTTP 响应时产生过 ConnectionAbortedError 日志；流程断言通过，未据此声称外部网络稳定。
- `node tools/check_stet_browser.cjs`：双语往返/刷新、正文和草稿不改写、设置分类保存、笔记评论检索、原生导入原件字节、指南与 390px 设置/笔记界面通过。检查中故意将伙伴名设成“设置”，确认它不会被界面翻译。

浏览器脚本仅访问各自的本地测试服务。合成截图保存在被忽略的 `.local/`，不含私人材料。实际 iPhone/Android、屏幕阅读器完整验收、所有供应商生成、所有真实导出变体、大库性能及跨模型人格实验尚未完成。本次 Windows 验证不能冒充其他平台实机验证。

## 工程设计与功能状态

[16-memory-persona-design.md](16-memory-persona-design.md) 是下一阶段工程方案：共享记忆策略、可选私人适配器、Colab 训练向导，以及 Listen / Notice / Know / Practice。六种实用策略替代神话角色名字。尚未训练、提供策略 API 或发布 HF 模型，当前界面不假装这些已可点击使用。

现有 `examples/governance-cases.json` 的 14 个案例仍是描述性规格；global/topical、target_message_ids、supersedes 和纠正成组预算不能计入已通过功能。原件不可悄悄覆盖、未知保持未知、推断与用户确认分开的要求继续适用。

## 交接与回退

完整源码保留 Git 历史，迁入 `7e84e40` 的既有体验修复后继续实施。实现与下载包提交 `04c082e` 已普通快进同步 main。随后依所有者明确授权，将同一仓库改名为 [Stet](https://github.com/OopsVeraHuang/Stet)；私有状态与许可证未变，不部署私人服务。实现提交及下载包哈希见 [在线交付记录](https://github.com/OopsVeraHuang/Stet/blob/main/downloads/README.md)。

文件清单用 `tools/package.py refresh` 从暂存 Git 字节生成；ZIP 只从干净提交导出。新包自带清单，可离线核对。下载包对应其记录的源码提交，随后上传包和补充交付说明的提交不改变包内代码。旧体验包保留，不覆盖。

回退先停止服务并备份整个独立 profile，使用旧版本源码和对应备份启动。此次没有破坏性数据库迁移；不把回退理解为可以忽略备份、覆盖正在使用的数据库。
