# Stet — Let it stand.

**User-Governed, Provenance-Preserving Memory for Long-Horizon Continuity Across LLMs**

**Language / 语言: English | [简体中文](README.md)**

[Getting started](docs/15-getting-started.en.md) · [Release checks](docs/17-stet-preview.md) · [Architecture proposal](docs/16-memory-persona-design.md#english-overview)

**[Download the bilingual preview](downloads/README.md)** · [GitHub](https://github.com/OopsVeraHuang/Stet)

## Why Stet?

***Stet*** is Latin for *let it stand*. In proofreading, dots beneath an edited passage and the instruction *stet* cancel a correction and restore the original wording. For an author responding to an edit, it is a compact assertion: **keep what I actually wrote.**

Long-term interaction with an AI involves more than a collection of facts. Wording, stance, hesitation and later corrections carry meaning across conversations. Memory pipelines built around background summaries or atomic fact extraction trade this context for efficiency through **lossy model-driven summarization**. They can flatten pragmatic detail and narrative structure; when an inference is stored as a user statement, later retrieval can give that error the appearance of evidence. Model switches and version updates introduce another source of discontinuity.

Stet takes an **Archive-First, User-Governed** approach. Original records remain available for inspection; summaries and indexes are replaceable interpretations. Users retain authority over corrections to their personal accounts, relationship definitions and enduring preferences. Stet brings this approach into a runnable personal research workspace for conversation, memory governance, co-reading and study.

## Core Designs & Architectural Commitments

Stet asks more than whether a retriever can return relevant text: **what qualifies as evidence for a response, who can revise its interpretation, and how does that revision remain accountable to its source?** Four commitments organize the architecture and research agenda.

| Design | Architectural commitment |
|---|---|
| **Archive-First Architecture** | Separate the **Permanent Archive**, **Disposable Index**, **Normative Governance** and **Ephemeral Context**. Indexes can be rebuilt and models replaced without allowing background summarization to silently overwrite the transcript. Preservation does not remove the user's right to delete records or withdraw an import. |
| **User-Governed Correction Override** | Distinguish direct user statements—**what is given**—from model-generated interpretations or dialogue—**what is inferred**. Corrections update the interpretation used in subsequent context while preserving the historical record. This separation makes the promotion of an agent's own words into purported user facts an explicit governance problem. |
| **Fine-Grained Provenance & Temporal Grounding** | Locate evidence by speaker, source scope, branch, available model metadata (`model_id`) and citation markers. Keep message time (`recorded_at`), ingestion time (`imported_at`) and the time of a narrated event distinct. The target assembly contract computes relative temporal relations per turn, grounding references such as “yesterday” in their original context. |
| **Cross-Model Continuity & Audited Ingestion** | Keep archives, corrections and interaction preferences outside any single provider, allowing adapters such as Gemini and DeepSeek to draw on the same external memory. Supported ChatGPT, Claude, Gemini Takeout and AI Studio text exports enter through previewable, idempotent imports with access to original files. Missing fields and unparsed attachments remain visible. |

> **The index is disposable; the verbatim record stands.**

See the [data contracts](docs/02-architecture.md) and [research questions and baseline comparisons](docs/01-project.md) for the design rationale.

## Key Workspace Capabilities

- **Provenance-grounded chat.** Switch response models within one workspace, inspect memory citations and return to source passages. Reviewable, revocable corrections support control over personal accounts and interaction preferences without rebuilding memory for each provider.
- **Multi-platform archive importer.** Preview supported JSON and ZIP exports before committing an import. Original bytes and file hashes remain available, alongside the branch information and timestamp precision supplied by the source. Duplicate detection and batch withdrawal make ingestion inspectable and reversible.
- **Side-by-side co-reading and library.** Read PDF and EPUB books alongside the conversation, and keep DOCX, Markdown and plain-text documents in a shared workspace. Co-reading uses the current passage or selection as its entry point rather than resending an entire book each turn.
- **Multilingual study and annotation.** Save messages, highlight passages, add comments and navigate back to the source conversation. Search quotations and annotations; use Chinese, English and Russian (CN / EN / RU) lexical memory retrieval, with an optional local multilingual semantic model. **Saved for Study does not imply Endorsed as Fact.** Notes and conversations share a retrieval system while retaining their source types.
- **Zero-key offline exploration.** Import archives, inspect original passages, read documents and annotate existing messages without an API key. Connect your own provider credentials when you want newly generated replies. Switch the interface between English and Simplified Chinese without translating or rewriting your records.

## Quick Start & Interactive Walkthrough

Use Python 3.11+. Download and extract the preview, then create a virtual environment in the project root. Initial setup time depends on dependency downloads.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -X utf8 -m continuity --open
```

On Linux/macOS, substitute `.venv/bin/python` for the virtual-environment interpreter path. After installation, Windows users can also double-click `启动原型.cmd`.

The CLI retains the `continuity` module name for compatibility with existing profiles in `~/.continuity/default`. The default port is 8780; add `--port 0` to select an available port. Give each instance its own directory with `--data-dir`.

### Out-of-the-Box Tour

1. **Bring in a shared history.** Open the archive importer, preview the synthetic JSON sample and confirm its six fictional records. Return to chat.
2. **Inspect the evidence.** Search Memory for `松湾` (the sample's fictional place name). Open a source passage to check the speaker, original file and available time information.
3. **Read alongside the conversation.** Import a PDF or EPUB into the bookshelf, or add a document to Files. Open the reading view and select a passage to discuss.
4. **Keep a passage worth revisiting.** Open Study mode for an existing message. Right-click or long-press to save it, add highlights and a comment, then use note search to find it and return to the original exchange.
5. **Extend on your terms.** Add your own Gemini or DeepSeek API key under Models & connections and enable requests to generate replies. For semantic memory retrieval, follow the [development guide](docs/10-cloud-development.md) to install `requirements-semantic.txt` and the local multilingual weights.

The [English guide](docs/15-getting-started.en.md) and [Chinese guide](docs/14-getting-started.md) cover supported export structures and everyday workflows.

## Repository Layout & Verification

| Path | Purpose |
|---|---|
| `app/` | Conversation workspace, provider adapters, memory, library, reading, notes and video |
| `continuity/` | Default CLI, archive ingestion and provenance management |
| `reference_core/` | Reference modules for retrieval and context policies |
| `examples/` / `tests/` | Synthetic archives, acceptance specifications and automated tests |
| `docs/` / `NEXT_AGENT.md` | Research design, architecture, guides and development handoff |
| `provenance-platform.json` / `THIRD_PARTY.md` | Code provenance, third-party components and design references |

With dependencies installed, run the local tests. The package verifier checks the integrity of a downloaded source package:

```text
python -m unittest discover -s tests -v
python tools/package.py verify
```

Tests use synthetic data and mocked provider responses, with **no paid API calls**. HTTP tests require a loopback port. Reproduction details are recorded in the [release checks](docs/17-stet-preview.md), [platform verification](docs/12-platform-migration.md) and [interaction checks](docs/13-experience-check.md). After editing source files, follow the [packaging guide](docs/09-verification.md) to refresh the manifest.

## Research Scope & Status

Stet is a **research artifact** for HCI, NLP and AI: an interactive environment in which to study user-governed memory and context assembly across models. Its central questions concern how users inspect and correct agent memory, which interaction patterns persist through model changes, and how evidence selection trades off against context cost and interaction quality. Personality continuity is a research question supported by this platform, to be assessed through longitudinal interaction and controlled comparisons.

The current implementation includes archive ingestion, chat, source retrieval, a persistent correction overlay, co-reading and study notes. Scoped corrections, automatic recall of corrections linked to historical messages, indivisible evidence-group budgeting, and the full event-time and relative-time assembly contracts remain on the implementation roadmap. Missing model, role or time metadata remains unknown. Memory-R2-inspired policy training and layered persona mechanisms are specified in the [engineering proposal](docs/16-memory-persona-design.md); they have not been trained or deployed. The [status document](docs/status.md) records implementation and validation evidence.

Synthetic tests establish software behavior; retrieval quality, cross-model personality continuity and actual spending require dedicated evaluation. Real-time video is **Beta**, with provider and mobile-device combinations requiring separate validation. Provider calls are billed independently; check model availability and prices before use. Remote access requires authentication and HTTPS. User authority over personal accounts and relationship preferences does not require uncritical agreement about external facts.

Private corpora, personal credentials, runtime profiles and model weights are excluded from the repository. Stet is currently a Research Preview; an overall open-source license has not been selected. Component licenses and research and tutorial acknowledgments are retained in [THIRD_PARTY.md](THIRD_PARTY.md); full tutorial PDFs are not distributed.
