# Continuity — Prototype 01

**User-governed memory for continuity across AI models.**

暂用工作名，尚未检查商标或项目重名。定位：支持长期关系与持续协作的个人 Agent 研究平台。

这是从 P0 起步包建设出的 **P1-A 本机记忆工作台**：可预览并确认导入规范 JSON/MD、浏览原文、按字面词句检索并打开出处。尚未接入语义模型、修正生效机制或回答模型，也没有公开发布。产品与研究计划、参考模块、虚构样例和离线测试继续保留。

先读 [面向非工程师的项目说明](docs/01-project.md)，再读 [实施顺序](docs/04-roadmap.md)。给下一位编码助手的任务在 [NEXT_AGENT.md](NEXT_AGENT.md)。本地与云端的使用步骤见 [开发环境说明](docs/10-cloud-development.md)。

## 先点起来

Windows：双击 `启动原型.cmd`（需要已有 Python 3.11+），浏览器会自动打开。

其他系统在本仓库目录运行：

```text
python -X utf8 -m continuity --open
```

无需安装额外包、填写 API key 或下载模型。只监听本机 `127.0.0.1`，自动选择空闲端口；关闭启动窗口或按 Ctrl+C 停止。运行数据保存在本仓库被 Git 忽略的 `.local/continuity/`，独立于任何其他项目。也可用 `--data-dir` 指定一个独立目录。

点击「预览 JSON 示例」→「确认导入」应得到 6 条记录；到「原文检索」查“松湾”应找到 2 条，点「查看出处」核对完整原文。再导入 MD 示例可查看不同分支，总计 10 条。详见 [三屏体验与局限](docs/11-p1a-workbench.md)。

云开发环境中的本机地址属于云端机器，不能在你的电脑直接打开。可从私有 PR 下载功能分支 ZIP，解压后双击启动文件；这不要求部署公网。

## 今天可以验证什么

安装有 Python 3.11+ 的电脑上，在此文件夹运行：

```powershell
python -m unittest discover -s tests -v
python tools/package.py verify
```

测试仅使用虚构文本和标准库，不连接外部网络，不使用模型 API，不下载模型，不涉及私人记录。P1-A 的 HTTP 集成测试需允许本机回环端口。也可双击 `检查交接包.cmd`，前提是电脑已安装可通过 `python` 或 `py` 调用的 Python。

`reference_core/` 是从私人先导系统整理的参考实现，不是独立的完整后端。语义检索需要额外模型、依赖和 API 适配器；基础测试不代表已验证语义召回质量。

## 文件怎么找

| 文件夹 | 用途 |
|---|---|
| docs | 定位、架构、实验设计、实施步骤、经验与发布边界 |
| continuity | P1-A 导入、SQLite 档案、本机服务与三屏界面 |
| reference_core | 词句与语义融合、时间处理、短窗口策略 |
| examples | 全部虚构的中英俄消息与评测用例 |
| tests | 不花 API 费用的基本回归测试 |
| provenance.json | 参考代码的来源哈希及处理记录 |

**没有打包**私人聊天、私人 persona、数据库、账单、账户登录、API key、服务器连接信息、电子书、音频、模型权重或第三方教程全文。

时间与纠正联动的新增契约见架构文档；`examples/governance-cases.json` 是下一阶段待实现的验收规格，不是已通过的功能测试。

工程使用 Git 保存版本，并向项目所有者指定的私有 GitHub 仓库同步。仓库保存净化起步包及后续原型工程；每位使用者的运行数据与凭据独立保存。尚未选择项目整体开源许可证，也没有公开发布；详见 `docs/07-release.md`。
