# 私有体验包下载

## 最新：Stet 双语预览 r2 · GitHub 地址修正版

[下载 Stet-Preview-2026-11-17-r2.zip](Stet-Preview-2026-11-17-r2.zip)。打开文件页，点击 **Download raw file / 下载原始文件**。当前仓库为 [OopsVeraHuang/Stet](https://github.com/OopsVeraHuang/Stet)，仍为私有；需要登录有权限的 GitHub 账户。

r2 更新中英 README、工程说明及交接词中的仓库地址，应用代码与上一版一致。已有安装无需迁移数据或重新填密钥；源码检出的 Git 远端可按 docs/10 更新。旧 ZIP 和 Git 历史保留原字节，包内 downloads 中的历史版本不作为当前地址参考。

- 来源提交：`e5e5bc85e0679359eed6cab8404954319a586179`。
- 大小：15,749,609 字节；含历史下载包，因此比首版大。
- SHA-256：`c6a80c0ce46430b48bbce2289b4925c9892b9227df0abb4c1905c6588f9827cc`。
- 351 个 ZIP 成员；全新解压后 350 个清单文件逐字节校验通过。
- 当前文本文件未再引用旧 GitHub 用户名；嵌套历史 ZIP 保持原样。
- 本次仅改文档与地址，沿用上一版 41 项测试与四套浏览器检查的适用范围；没有重跑或声称新增功能验收。

English: **[Download the r2 address update](Stet-Preview-2026-11-17-r2.zip)** and use **Download raw file** on the file page. Follow README.en.md after extraction. This revision updates repository links to `OopsVeraHuang/Stet`; application code is unchanged. Existing profiles and credentials require no migration. Historical archives remain unchanged for reproducibility.

## 历史版本：Stet 双语预览 · 2026-11-17

[下载 Stet-Preview-2026-11-17.zip](Stet-Preview-2026-11-17.zip)。打开文件页后点右上角 **Download raw file / 下载原始文件**。解压后按 README 安装依赖，Windows 可用 `启动原型.cmd` 启动。中英文完整指南在 docs/14 和 docs/15；应用内侧栏也可打开。此包为源码体验包，不是免安装 EXE，不包含 API key、私人档案或模型权重。

- 实现提交：`a0413edc8c8898fc0f1c05b0cad68241d7eb065f`。
- 大小：7,897,796 字节。
- SHA-256：`7f061dd2451f982d8305fba5d64d7cec5c78035dffb398758425a29935e62582`。
- 350 个成员（349 个清单文件 + 清单本身）。包内保留旧下载版本和历史说明；当前入口仍为 Stet。
- 新增：中英 UI、笔记/评论搜索、原生平台文字导入、设置分类、使用说明；视频 Beta，工作室隐藏。
- 41 项离线测试及四套浏览器流程通过；具体边界见 docs/17-stet-preview.md。记忆策略训练和分层人格仅为 docs/16 的工程提案。
- 此 ZIP 已在全新解压目录再次通过 349 个文件校验及 41 项离线测试。

仓库已按所有者授权改名为 [Stet](https://github.com/OopsVeraHuang/Stet)，仍为私有。包内少量历史仓库名称/链接反映打包时的版本；当前下载入口以上述新地址为准，应用名称已经是 Stet。

此后上传 ZIP 和补充说明的提交不改动包内代码。校验命令：`python tools/package.py verify`；测试使用安装好 requirements.txt 的 Python 环境。仓库保持私有，登录有访问权限的 GitHub 账户后下载。没有订阅服务或公网部署。

English: download the file above using **Download raw file**, unzip it, and follow README.en.md. This is a source preview, not a standalone installer. Choose English in the sidebar. The package corresponds to the source commit and SHA-256 above; runtime data and credentials are excluded. Training and persona layers remain proposals.

## 历史版本：Continuity

这是完整 Continuity 平台体验包，供无法从云端工作区下载文件时使用。仓库保持私有。

点击 [Continuity-platform-experience-2026-10-27.zip](Continuity-platform-experience-2026-10-27.zip)，在文件页右上角点击 **Download raw file / 下载原始文件**（向下箭头）。需要登录有权访问此仓库的 GitHub 账户。无需使用 Code → Download ZIP；后者下载的是整个分支。

下载后应得到约 3.8 MiB 的 ZIP。先解压，再按包内 README 安装依赖和启动。这不是免安装的可执行程序，也不包含 API 密钥或模型权重。

- 内容：完整平台，包含聊天、阅读器、资料库、学习笔记、记忆、工具与视频代码，以及本轮体验修复。
- 源代码提交：`1fdb50cf3cb5d5b4548577fc87a7c2fc72f3b0d5`。
- 文件大小：3,939,628 字节。
- SHA-256：`471badef0aa5c121b0bde07d837fde2f40747f1ccd754dda969d22ea4dcb6e82`。
- 包内 335 个成员（334 个清单文件及清单本身），精确字节校验通过；原交付已在全新解压目录通过 34 项离线测试。

这份 ZIP 保留原交付的精确字节，不随之后的仓库文档更新自动改变。未来版本另存新文件名。它不包含私人记录、运行 profile、凭据或本次下载说明；完整验证范围见包内 docs/13-experience-check.md。
