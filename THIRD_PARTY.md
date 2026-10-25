# 第三方组件与参考来源

## 随包组件

| 组件 | 版本/来源 | 许可文件 |
|---|---|---|
| PDF.js / pdfjs-dist | 6.3.289；https://github.com/mozilla/pdf.js | app/static/vendor/pdfjs/LICENSE，Apache-2.0；子目录字体许可保留 |
| foliate-js | commit 78914aef4466eb960965702401634c2cb348e9b1；https://github.com/johnfactotum/foliate-js | app/static/vendor/foliate/LICENSE，MIT |

来源压缩包与校验记录见 app/static/vendor/VERSIONS.json。本次仅继承阅读组件及许可，没有电子书或用户素材。第三方组件不作为本项目原创研究贡献。

## 可选模型（不随包分发）

[Xenova/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2) 是 [原 sentence-transformers 模型](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) 的 ONNX 转换，用于语义向量，不生成回答，也不是本项目训练的人格模型。固定 revision 和 SHA-256 在 examples/semantic-model.json。使用前阅读上游模型卡与许可。

Python 依赖由使用者另行安装，见 requirements 文件；保留各自许可。项目整体许可证未选择。

## 教程与设计启发

先导系统参考了用户提供的《StarHub记忆系统教程···SPEC_》和《StarHub实时视频陪伴教程···专注模式》。影响集中在原文记忆维护以及视频观察、语音回合、记忆校准的设计讨论。这是设计参考，不代表实现完全相同、作者背书或结论已经验证。

当前缺少可核实的作者署名、版本日期和稳定公开地址，发布前补齐准确书目信息。保留标题与来源关系，不附全文、不复制作者私有代码；不能因为排除全文而抹去致谢。取得可靠链接后可添加到这里。

Mem0/Letta 的基线比较见 docs/01-project.md，未复制其代码。净化先导代码的来源说明见 provenance-platform.json，没有私人路径或聊天样本。
