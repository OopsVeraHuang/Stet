# Stet — Let it stand.

**User-Governed, Provenance-Preserving Memory for Long-Horizon Continuity Across LLMs**

用户可治理、保留原件出处的跨模型长程交互记忆系统。

**语言 / Language：简体中文 | [English](README.en.md)**

[中文使用指南](docs/14-getting-started.md) · [本版验收](docs/17-stet-preview.md) · [记忆与人格工程设计](docs/16-memory-persona-design.md)

**[下载 Stet 双语预览包](downloads/README.md)** · [GitHub](https://github.com/OopsVeraHuang/Stet)

## 为什么是 Stet？

***Stet*** 源自拉丁语，意为 *let it stand*。在手稿校勘与出版中，编辑者在被删改的文字下加点、旁注 *stet*，表示撤销这次涂改，恢复原文。它也可以表达作者对修改的回应：**保留我原本说过的话。**

当 AI 成为长期的研究伙伴、创作搭档或陪伴者，记忆就不只是“记住几个事实”。措辞、说话人的立场、一次犹豫与后来的修正，共同构成了交互的意义。依赖后台摘要或原子事实提取的记忆流程，以**模型驱动的有损压缩（Lossy Model-Driven Summarization）**换取上下文效率，也可能抹平语用细节与叙事脉络；一旦模型的推断被当作用户陈述保存，错误便可能在后续召回中不断获得“证据”。更换模型或升级版本，又给长期形成的交互方式带来新的断裂风险。

Stet 的主张是：**原件优先，治理归人（Archive-First, User-Governed）。** 原文是可以回查的底本，摘要与索引是可以替换的解释工具；个人陈述、关系定义与长期偏好的修正权归用户。Stet 将这一主张落实为一个可运行的个人研究与交互工作台，把对话、记忆治理、共读与学习放在同一个可审计的环境中。

## 核心设计与架构主张

Stet 关注的不是单次检索能返回多少文字，而是：**哪些记录有资格成为本轮回答的依据，谁能修订这些依据，以及修订后如何继续保留出处。** 以下四项原则组织系统架构与研究路线。

| 核心设计 | 架构主张 |
|---|---|
| **四层解耦 · Archive-First Architecture** | 分离长期原始档案（Permanent Archive）、可丢弃派生索引（Disposable Index）、用户显式治理（Normative Governance）和单轮临时上下文（Ephemeral Context）。索引可重建，模型可替换；后台摘要不得静默覆盖对话底本。原件保留不剥夺用户主动删除或撤回导入的权利。 |
| **显式纠错覆盖 · User-Governed Correction Override** | 区分用户的直接陈述（What is given）与模型的推演或台词（What is inferred）。用户修正用于更新后续上下文中的解释，历史原文仍然可查。将推断与用户确认分层，针对“模型把自己的旧台词当成用户事实”的级联错误建立可审计的治理边界。 |
| **细粒度溯源与时间锚定 · Provenance & Temporal Grounding** | 以说话人、来源范围、分支、可得的生成模型元数据（`model_id`）与引用标记定位证据。区分消息记录时间（`recorded_at`）、导入时间（`imported_at`）和文中事件时间；目标组装契约按轮计算相对时间关系，避免把数小时前、数年前与当前发生的事混为一谈。 |
| **跨模型连续性与可审计导入 · Cross-Model Continuity & Audited Ingestion** | 将档案、修正与交互偏好置于供应商之外，让 Gemini、DeepSeek 等适配器使用同一套外部记忆。ChatGPT、Claude、Gemini Takeout 和 AI Studio 的已适配文字导出可预览、幂等导入并回查原件；缺失字段和未解析附件明确呈现，不包装成完整成功。 |

> **The index is disposable; the verbatim record stands.**
>
> 索引可以重建，原话应当留存。

详细的数据契约见[架构说明](docs/02-architecture.md)，研究问题与基线比较见[项目定位](docs/01-project.md)。

## 平台核心功能

- **带出处检索的跨模型对话。** 在同一工作台切换回答模型，查看记忆引用、回到原文，并通过可查看、可撤回的澄清记录调整个人事实与交互偏好。记忆不必随供应商重建。
- **跨平台历史导入工作台。** 从已适配的 JSON 或 ZIP 导出开始，先预览角色、记录与遗漏，再确认导入。原文件按字节保存并记录哈希，保留来源可提供的分支与时间精度，支持重复导入识别和整批撤回。
- **并排共读与共享资料库。** 在 PDF / EPUB 书架中边读边聊，把 DOCX / MD / TXT 等资料放入共享工作区。共读以当前片段和选文作为讨论入口，无需每轮发送整本书。
- **多语种研究与学习模式。** 收藏消息、标注重点、添加评论，并从笔记返回原对话；搜索同时覆盖摘录与批注。记忆检索支持中文、英文、俄文（CN / EN / RU）词句与可选的本地多语言语义模型。**作为学习材料收藏（Saved for Study），不自动等于认可其为事实（Endorsed as Fact）。** 笔记与聊天接入同一记忆系统，并保留各自的来源类型。
- **免密钥离线探索。** 无需 API Key 即可导入历史、检索原文、阅读资料，并对已有消息做学习批注。需要新生成的模型回答时，再接入自己的密钥。界面可在简体中文与 English 之间切换，原始记录与笔记保持原文。

## 三分钟快速体验

准备 Python 3.11+，下载并解压预览包，在项目根目录创建独立环境。首次安装时间取决于依赖下载速度。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -X utf8 -m continuity --open
```

Linux / macOS 使用 `.venv/bin/python` 替代上述虚拟环境解释器路径。Windows 完成安装后可双击 `启动原型.cmd`。

CLI 入口沿用 `continuity` 模块名，以保持已有数据目录 `~/.continuity/default` 的向后兼容。默认端口为 8780，可加 `--port 0` 自动选择；使用 `--data-dir` 为不同实例指定独立资料目录。

### 开箱导览

1. **带入一段共同经历。** 打开「导入历史记录」，预览 JSON 合成示例，确认导入 6 条虚构记录，再点击「回到对话」。
2. **检查记忆的证据。** 在「记忆」搜索“松湾”，打开出处，核对谁说了什么、来自哪份原件，以及时间是否已知。
3. **开始并排共读。** 在「书架」导入一本 PDF / EPUB，或向「资料库」添加文档。打开阅读与对话视图，选择准备讨论的片段。
4. **把重要的话留下来。** 对已有消息开启「学习模式」，右键或长按收藏，添加高亮和评论；用笔记检索框找回它，再跳回原对话。
5. **按需扩展。** 在「连接与预算」填入自己的 Gemini / DeepSeek API Key 并启用调用，即可生成新回复。也可按照[开发说明](docs/10-cloud-development.md)安装 `requirements-semantic.txt` 和本地多语言权重，为记忆增加语义召回。

更多操作与导入格式说明见[中文指南](docs/14-getting-started.md)与[英文指南](docs/15-getting-started.en.md)。

## 仓库结构与验证

| 路径 | 内容 |
|---|---|
| `app/` | 对话工作台、模型适配、记忆、资料库、阅读、笔记与视频模块 |
| `continuity/` | 默认 CLI 入口、原件导入及出处管理 |
| `reference_core/` | 检索与上下文策略的参考模块 |
| `examples/` / `tests/` | 合成档案、验收规格与自动化测试 |
| `docs/` / `NEXT_AGENT.md` | 研究设计、架构、使用指南与开发交接 |
| `provenance-platform.json` / `THIRD_PARTY.md` | 代码来源记录、第三方组件与设计参考 |

安装依赖后运行本地测试；文件校验命令用于核对下载包的完整性：

```text
python -m unittest discover -s tests -v
python tools/package.py verify
```

测试使用合成数据与模拟供应商响应，**不消耗付费 API**；HTTP 测试需要本机回环端口。浏览器检查和复现环境见[本版验收](docs/17-stet-preview.md)、[平台验证](docs/12-platform-migration.md)与[体验验证](docs/13-experience-check.md)。修改源码后的清单维护见[打包与校验说明](docs/09-verification.md)。

## 研究范围与方法论边界

Stet 是面向 HCI / NLP / AI 研究的 **Research Artifact**，将可溯源、可撤回的记忆治理界面与跨模型上下文组装置于同一实验平台。研究重点包括：用户如何理解并修正 Agent 的记忆；基础模型更换后哪些交互特征能够延续；证据召回、上下文成本与交互质量之间如何取舍。人格连续性是这一平台支持的研究议题，其效果需要纵向交互与受控比较来评估。

当前版本已提供原件导入、对话、出处检索、常驻澄清覆盖层、共读与学习笔记。作用域化纠正、关联旧记忆的自动纠正召回、不可拆分的证据组预算，以及完整的事件时间与相对时间组装契约，属于后续实现；来源缺失的模型型号、角色或时间保持未知。Memory-R2 启发的训练策略与分层人格机制见[工程提案](docs/16-memory-persona-design.md)，尚未训练或部署。实现进度与验证记录集中维护于[状态文档](docs/status.md)。

现有合成测试验证工程行为；检索质量、跨模型人格连续性与真实费用仍需专门评测。实时视频通话处于 **Beta**，真实供应商和移动设备组合需分别验收。API 调用按供应商计费，使用前需核对模型可用性与价格；远程访问需独立认证和 HTTPS。用户对个人陈述与关系偏好的治理权，不意味着模型必须无条件认同外部事实判断。

私有语料、个人凭据、运行资料目录和模型权重均排除在仓库之外。仓库目前为研究预览版（Research Preview），整体开源许可证尚未选定；第三方组件许可及论文、教程启发保留于[来源说明](THIRD_PARTY.md)，不随包分发完整教程 PDF。
