# Continuity — Prototype 01

**User-governed memory for continuity across AI models.**

暂用工作名，尚未检查商标或项目重名。定位：支持长期关系与持续协作的个人 Agent 研究平台。

这是 **P0 原型开发交接仓库**，不是已经可安装使用的完整 Web App，也没有公开发布。它包含产品与研究计划、工程路线、经过筛选的记忆模块、完全虚构的样例及离线测试。完整界面、服务端适配器和供应商接口将在新开发窗口接入。

先读 [面向非工程师的项目说明](docs/01-project.md)，再读 [实施顺序](docs/04-roadmap.md)。给下一位编码助手的任务在 [NEXT_AGENT.md](NEXT_AGENT.md)。本地与云端的使用步骤见 [开发环境说明](docs/10-cloud-development.md)。

## 今天可以验证什么

安装有 Python 3.11+ 的电脑上，在此文件夹运行：

```powershell
python -m unittest discover -s tests -v
python tools/package.py verify
```

测试仅使用虚构文本和标准库，不连接网络，不使用 API，不下载模型，不涉及私人记录。也可双击 `检查交接包.cmd`，前提是电脑已安装可通过 `python` 或 `py` 调用的 Python。

`reference_core/` 是从私人先导系统整理的参考实现，不是独立的完整后端。语义检索需要额外模型、依赖和 API 适配器；基础测试不代表已验证语义召回质量。

## 文件怎么找

| 文件夹 | 用途 |
|---|---|
| docs | 定位、架构、实验设计、实施步骤、经验与发布边界 |
| reference_core | 词句与语义融合、时间处理、短窗口策略 |
| examples | 全部虚构的中英俄消息与评测用例 |
| tests | 不花 API 费用的基本回归测试 |
| provenance.json | 参考代码的来源哈希及处理记录 |

**没有打包**私人聊天、私人 persona、数据库、账单、账户登录、API key、服务器连接信息、电子书、音频、模型权重或第三方教程全文。

时间与纠正联动的新增契约见架构文档；`examples/governance-cases.json` 是下一阶段待实现的验收规格，不是已通过的功能测试。

工程使用 Git 保存版本，并向项目所有者指定的私有 GitHub 仓库同步。仓库保存的是这个净化起步包；每位使用者的运行数据与凭据独立保存。尚未选择项目整体开源许可证，也没有公开发布；详见 `docs/07-release.md`。
