# 本地、GitHub 与云端开发

Git 是修改历史；GitHub 是存放这份历史的远程仓库；Codex 云环境是在另一台机器上读写代码、运行测试的开发环境。应用服务器才负责持续提供聊天网页。仓库上传不会自动启动完整应用，也不会同步任何使用者的 SQLite 数据库。

## 当前阶段

本仓库仍为 P0：文档、四个参考模块、合成样例和离线测试。没有 Web 服务启动命令，没有必须填写的 API key，没有必须下载的语义模型。本阶段无需购买额外服务或开启 GitHub Actions/Codespaces。

本地和云端均使用 Python 3.11+；建议云环境选 Python 3.12。基础检查只用标准库，不需要 pip install。在仓库根目录执行：

```text
python -X utf8 -m unittest discover -s tests -v
python -X utf8 tools/package.py verify
```

Linux 若只有 `python3`，将命令里的 `python` 换成 `python3`。Windows 的 `检查交接包.cmd` 不是 Linux 启动脚本。8 项测试通过只证明现有参考函数；新增治理案例的状态仍是 `planned_not_executable`。

## 云环境设置页可以直接粘贴

> 请使用我选中的这个私有仓库，检查 main 的最新提交。读取 README.md 和 AGENTS.md。这是仅使用 Python 标准库测试的 P0 交接工程，请准备 Python 3.12 并运行上述两条离线检查。不要安装 Web 框架、下载模型、填写供应商密钥或启动付费服务。记录实际检查结果和环境；如果没有应用入口，请如实说明本阶段只有文档、参考模块和测试。准备完成后给出配置报告。

设置任务完成后，检查报告并在界面选择发布环境，再开始新任务。云环境的“发布”是保存供后续任务使用的开发环境，不是公开 GitHub 仓库或部署网站。若旧环境是在空仓库上建立的，重新打开环境设置核验最新文件与检查结果。仅凭仓库上传成功不能宣称云环境已发布或 Linux 测试已通过。

参考：[Codex 云环境官方文档](https://learn.chatgpt.com/docs/environments/cloud-environments)（2026-10-24 核对）。

## 开始原型开发

在新的本地或云端任务中粘贴 `NEXT_AGENT.md` 的全部内容。任务必须检出本仓库，先核对分支和现有修改，再从 P1-A 开始。完成一个切片后保存提交、更新功能状态；功能修改建议走分支/PR。未提交或未推送的本地改动不会自动出现在别的电脑。

GitHub 连接器的授权与电脑 Git 的登录可能是分开的。保留完整提交历史的 push 如需登录，使用 Git Credential Manager 的正常 GitHub 登录流程，不把密码、访问令牌或 OAuth 文件放进聊天、仓库或交接包。
