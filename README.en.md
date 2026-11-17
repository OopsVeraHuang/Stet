# Stet — Let it stand.

**User-governed memory for continuity across AI models.**

**Language / 语言: English | [简体中文](README.md)**

[Getting started](docs/15-getting-started.en.md) · [Architecture proposal](docs/16-memory-persona-design.md#english-overview)

**[Download the bilingual preview](downloads/README.md)** — source package, checksum and installation steps.

Stet is a personal agent research platform for long-term collaboration, learning and companionship. You define the relationship. It opens to a real chat interface with a charcoal and violet theme, alongside source-linked memory, a document library, a PDF/EPUB reader and paper-toned study notes. Video is **Beta**; Studio is currently hidden.

Repository: [OopsVeraHuang/Stet](https://github.com/OopsVeraHuang/Stet). Portfolio description: **Stet — A research prototype for user-governed agent memory and continuity across AI models.** This is a private preview; personality continuity is a research objective, not a validated outcome.

## Run locally

Use Python 3.11+ (this preview was checked on Python 3.12). Create a virtual environment, then install the application dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -X utf8 -m continuity --open
```

On Linux/macOS, use `.venv/bin/python`. On Windows, after setup you can double-click `启动原型.cmd`. The `continuity` command and `~/.continuity/default` data folder remain for compatibility with earlier previews. Use a separate `--data-dir` for each profile. The default server is local to your computer, not a public website.

## Start without an API key

- Import chats: preview the synthetic sample, confirm, search and inspect its original source.
- Supported native text shapes: ChatGPT and Claude `conversations.json`; Gemini Takeout JSON; AI Studio JSON. Selected conversation JSON inside ZIPs is supported. Missing roles or times remain unknown. Attachments, audio and images are not extracted; some exports need conversion. [Exact boundaries](docs/15-getting-started.en.md).
- Open PDF/EPUB books or add documents in Files. No paid model is needed for local reading or search.
- Study mode saves messages, adds highlights/comments and searches passages or comments. Notes participate in the same memory system; saving a passage does not make it a confirmed fact.
- Switch Chinese/English in the sidebar. This changes interface labels, never your transcripts or notes.

For generated replies, use **Models & connections** to save your own Gemini or DeepSeek API key and explicitly enable paid requests. Settings separate connections, response/memory controls, companion preferences, web tools and spending. Provider model names/prices are inherited snapshots; check current availability and rates. The optional GPT subscription bridge requires separate integration and authentication; it is not ready to use in this preview.

Video requires a compatible provider connection and device permissions. Foreground use only; real devices and provider calls were not tested for this release. Remote/mobile access needs a separate authenticated HTTPS deployment.

## Evidence and next steps

Tests use synthetic data and mocked model responses. They do not establish personality persistence, retrieval quality on private archives, or lower real bills. See [release checks](docs/17-stet-preview.md) and [status](docs/status.md).

The [memory and persona proposal](docs/16-memory-persona-design.md) distinguishes today's features from planned Memory-R2-inspired policies and Alicia-inspired layers. No personalized model has been trained or published. Imported originals, credentials, private profiles and model weights stay outside Git.

The repository remains a private release candidate. An overall open-source license has not been selected. Third-party components retain their licenses; research and tutorial inspirations remain credited in [THIRD_PARTY.md](THIRD_PARTY.md). No full tutorial PDFs are bundled.
