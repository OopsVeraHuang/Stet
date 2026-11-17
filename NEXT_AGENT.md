# 下一窗口：继续完整交互平台，不从零重做

请在此独立库继续 Stet（原名 Continuity）。用户明确要求继承先导应用完整体验：聊天、模型选择、工具、记忆、灰紫 UI、阅读器、资料库、米色学习笔记、视频与窄屏界面；不要再次缩成绿色 RAG 管理后台。

当前私有仓库为 https://github.com/OopsVeraHuang/Stet，Git 远端为 https://github.com/OopsVeraHuang/Stet.git。Stet 双语预览交付已同步到 main；先 fetch 并核对 docs/status.md 和 downloads/README.md 的最新提交。不要再检出过时的 P0 基线重新造工作台。当前功能、检查和边界见 docs/17-stet-preview.md。

先读 AGENTS、README、docs/01-project、02-architecture、04-roadmap、12-platform-migration 和 status。`app/` 已迁入净化后的功能代码，`continuity/` 保留原件导入工作台。默认入口 `python -m continuity` 是聊天平台，导入入口在 /import/。旧“先从三屏空壳做起”的交接词已撤销。

新增中英 UI、原生平台文字导入、笔记搜索、分类设置、双语指南；视频 Beta，工作室隐藏。启动命令/资料目录仍为 continuity，不能为改名移动用户数据库。i18n 仅翻译界面，必须保护原文、批注和用户命名。运行 tools/check_stet_browser.cjs 与原有三套浏览器检查。

下一步工程按 docs/16-memory-persona-design.md：先 M0/M1/P1（可观察基线、纠正联动/策略接口、可编辑人格版本），再共享策略模型比较和训练。Memory-R2 是提取/管理策略研究，不能宣传为已经为每人训练专属检索器。原型中没有训练权重或一键 Colab 服务；无需替用户创建账号、上传私聊或订阅算力。

安装 requirements.txt 后运行离线测试；可选语义及浏览器检查见开发说明。没有 API 时展示真实空状态，不伪装回复。Gemini/DeepSeek 适配器和离线工具闭环已迁入，供应商实际调用与当前价格/模型可用性未验收。GPT 订阅桥仍未配置独立认证，不能读取本机其他任务登录。视频 relay 可启动，真实通话/手机锁屏未验收；远程部署需独立账号与 HTTPS。

新治理契约仍待实现：global/topical、target_message_ids、supersedes、关联纠正与旧原文的成组预算裁剪。现有澄清是有来源、可撤回的常驻覆盖层，并非上述联动算法；引用语境识别待增强。examples/governance-cases.json 仍为待实现规格，不能计入通过数。事件时间与记录时间不同，未知不猜测。

不修改私人 companion 的代码、服务器、账户、数据或人格。示例只用虚构资料。保留教程致谢，不上传全文、账单、声音或凭据。用户近期昂贵账单属于私人应用，不能把本库改进当成私人应用已省钱的证据。

记忆是研究重点，配套交互同样属于产品。用中文说明改了什么、点哪里、验证范围。每次更新状态与哈希清单；分支和 PR 可同步指定私有仓库，不强推或公开发布。新订阅、真实付费测试和部署另行明确范围。
