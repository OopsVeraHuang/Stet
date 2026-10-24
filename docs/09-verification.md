# 交接包验证

当前 P1-A 已在 Linux / Python 3.12.14 完成 25 项标准库测试与浏览器点击检查。详细范围见 `docs/status.md`；下方 2026-10-23 的 8 项结果和限制是 P0 历史记录。当前包仍用本文的暂存字节清单流程校验，不能把历史结果当作当前功能证据。

2026-10-23，在 Windows/Python 3.12 环境运行已有检查：

```text
python -X utf8 -m unittest discover -s tests -v
Ran 8 tests ... OK
```

覆盖排名融合、重复原文、短窗口承接、未知日期、日历周、日期候选排序、跨文字体系字面加分规则及西里尔字词提取。输入都是虚构数据。这 8 项检查不因新增设计文档而变成完整记忆系统测试。

没有运行真实 embedding、真实模型回答、端到端 Web UI 或参与者实验；也不能据 Windows 通过声称 Linux/Codex 云环境已经验收。`examples/governance-cases.json` 是下一阶段的描述性验收规格，尚未绑定运行时实现，不能计入通过数。

## 可复跑的打包步骤

`tools/package.py` 只需 Python 3.11+ 标准库。`refresh` 和 `build` 还需要 Git；解压后 `verify` 不需要 Git。所有步骤均不调用模型、不下载权重、不联网。

先检查 `git status` 和实际待提交文件，用明确文件路径暂存经过审查的修改；不要对带有私人导入资料的目录盲目执行整目录暂存。随后：

```text
python -X utf8 tools/package.py refresh
git add PACKAGE_MANIFEST.json
git diff --cached --stat
git commit -m "Update curated prototype handoff"
python -X utf8 tools/package.py build
```

顺序必须是“暂存工程文件 → refresh → 暂存清单 → 提交 → build”。`refresh` 读取 Git 暂存区的精确 blob 字节；排除清单自身，避免自引用哈希。`build` 要求工作区干净，从已提交 HEAD 导出，固定 `core.autocrlf=false`，核对 ZIP 文件集合与清单完全一致后才写文件。它不包含 `.git`、未跟踪文件和运行态数据，不覆盖已存在的 ZIP；再次打包用 `--output dist/新的文件名.zip`。

把生成的 ZIP 解压到一个新的空目录，在解压后的目录运行：

```text
python -X utf8 tools/package.py verify
python -X utf8 -m unittest discover -s tests -v
```

`verify` 检查清单内每个文件的存在、字节数及 SHA-256，拒绝不安全路径和符号链接。它不要求解压目录里完全没有额外文件，因为后续运行 Python 可能生成缓存；ZIP 的精确成员检查由 `build` 完成。内容被修改或缺失时应报错并返回非零退出码。

旧 Windows 工作区曾因 Git 配置使用 CRLF，与发布包的 LF 字节不同。本轮新增 `.gitattributes` 固定文本为 LF，新检出与 ZIP 的字节应保持一致。跨机器验收仍使用精确字节，不悄悄归一化已经修改的文件。`provenance.json` 保留最初 CRLF 整理哈希，并补充 `git_blob_sha256`；当前完整包以 `PACKAGE_MANIFEST.json` 为准。

## 发布检查边界

打包只包含经过暂存和提交的文件，并不自动判断其隐私或版权。推送前仍需检查完整 Git 历史、当前文件、ZIP 成员、私人姓名/路径/服务器标识、常见凭证模式，以及是否混入聊天、数据库、媒体、原始日志或模型权重。扫描未命中不等于绝对无泄漏；本轮审查不替代后续每次变更的检查。

已继承的历史有 3 次提交：最初清单使用 Windows 工作区字节，后两次已修正为 Git 导出字节。保留历史，不为修正旧清单而改写提交；只从当前经核验的提交生成交接包。
