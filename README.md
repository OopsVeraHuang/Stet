# Stet — Let it stand.

**User-governed memory for continuity across AI models.**

[English](README.en.md) · [中文使用指南](docs/14-getting-started.md) · [本版验收](docs/17-stet-preview.md) · [记忆与人格工程设计](docs/16-memory-persona-design.md)

**[下载 Stet 双语预览包](downloads/README.md)**（含校验值与安装步骤）。

2026-11-17：原型更名 **Stet（let it stand）**。可在侧栏切换中文/English；保留原来的 `continuity` 启动命令和数据路径，已有数据不搬动。视频标为 Beta，工作室暂时隐藏。设置按模型连接、回答与记忆、伙伴偏好、联网工具、费用分组。

支持长期协作、学习与陪伴的个人 Agent 研究平台，关系由用户定义。工作名未检查重名。

**默认打开聊天，继承先导应用的灰紫 UI。** 聊天、模型选择、带出处记忆、资料库、PDF/EPUB 共读、米色学习笔记与视频模块已迁入独立原型；原 JSON/MD 工作台保留为导入入口。功能迁入不代表所有供应商或真实手机功能已验收。[功能与验证边界](docs/12-platform-migration.md)

## 启动

需要 Python 3.11+。独立虚拟环境安装依赖（一次性下载，不订阅服务）：

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -X utf8 -m continuity --open
```

Windows 完成安装后双击 `启动原型.cmd`。Linux/macOS 使用 `.venv/bin/python`。默认端口 8780，被占用可加 `--port 0` 自动选择。数据默认在 `~/.continuity/default`，可用 `--data-dir` 指定独立目录。每个实例须用不同目录；Git 不包含数据和凭据。

没有密钥也可以导入、查原文、编辑资料、阅读和做笔记。生成回答需要在「连接与预算」填写自己的 Gemini/DeepSeek 密钥并启用调用。默认关闭模型调用；价格和模型目录是继承快照，须核对后使用。不会读取私人应用账户。

## 可以怎样体验

1. 「导入历史记录」→ 预览 JSON 示例 → 确认导入：6 条虚构记录。点击「回到对话」。
2. 「记忆」搜索“松湾”核对原文；聊天也从同一导入档案检索，不生成假的演示回复。
3. 「资料库」上传 PDF/DOCX/TXT/MD 或创建文字文件；「书架」导入 PDF/EPUB，与聊天并排，讨论只带当前片段。
4. 有对话后开启「学习模式」，右键/长按消息收藏、批注、返回原对话。笔记参与同一检索；收藏不自动等于用户认可。
   新增检索框，可同时查摘录与自己的评论，支持中英俄文字。
5. 「视频」有本地预览与通话入口。通话需密钥且会计费，实机和 iPhone 尚待验收；后台/锁屏通话不支持。预览不上传。

可选本地中英俄语义检索需要 requirements-semantic.txt 和独立权重，见 [开发说明](docs/10-cloud-development.md)。未安装时仍可词句检索，不会自动改用付费 embedding。

支持预览 ChatGPT / Claude 的 conversations.json、Gemini Takeout JSON、AI Studio JSON，以及含一个可识别会话 JSON 的 ZIP。保留原件，按已知结构导入文字；附件和未知格式不冒充已解析。格式、32 MiB 限制及缺失字段说明见使用指南。

## 最近的体验修复

聊天文字草稿支持刷新和导入页往返恢复；提交等待期间防止重复点击；阅读文字失败可重试；共读附件可返回正常聊天。保留灰紫聊天与米色学习界面。具体操作、保存边界及 Linux 验证见 [完整体验验收](docs/13-experience-check.md)。

## 验证

```text
python -m unittest discover -s tests -v
python tools/package.py verify
```

测试用合成资料和模拟供应商响应，不调用付费 API；应用测试需要 requirements.txt。HTTP 测试需回环端口。合成通过不证明人格稳定、真实账单降低或用户研究成功。

| 路径 | 内容 |
|---|---|
| app | 净化后的平台、工具、阅读/笔记、视频、记忆 |
| continuity | 原件导入工作台、默认启动入口 |
| reference_core | 最初保留的记忆参考模块 |
| examples / tests | 合成记录、验收规格和运行测试 |
| docs / NEXT_AGENT.md | 架构、来源、验证和交接 |
| provenance-platform.json / THIRD_PARTY.md | 来源哈希与第三方说明 |

新治理契约仍待实现，见 [架构](docs/02-architecture.md)。完整平台承载研究，不能缩成只有查询框。StarHub 教程保留致谢，不分发全文。私人原文、人格样例、账单、部署、声音、凭据和模型权重未打包。仓库保持私有，整体开源许可证未选择。
