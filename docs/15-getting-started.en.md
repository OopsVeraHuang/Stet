# Stet · Getting started

**Let it stand.** Keep the original words, and the right to reinterpret them. Formerly Continuity, Stet is a self-hosted interaction platform preview, not a hosted account service.

## Run locally

Download and unzip the source or verified preview package into a new folder. Install Python 3.11+ (validated here with 3.12). First-time dependency installation needs internet access, but does not download model weights or make paid model requests.

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m continuity --open
```
macOS / Linux:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m continuity --open
```

After setup, use the Windows launcher or repeat the last command. Keep the terminal running; Ctrl+C stops the service. If the port is occupied, add `--port 0` and open the printed URL.

The Python command and default storage path stay `continuity` and `~/.continuity/default` for backward compatibility. Use `--data-dir <path>` for an independent profile. Stop the service before backing up the entire profile directory. Never share a profile directory between users or commit it to Git.

## Explore without an API key

Choose English in the sidebar. Language selection changes interface copy, not your records, notes or the agent's replies. Open **Import chats → Preview JSON example → Confirm import**. Examples are synthetic. Find a phrase in **Memory** and inspect its source. Import an EPUB/PDF into **Bookshelf**, or PDF/DOCX/TXT/Markdown into **Files**. Page turns and imports do not call a model. Scanned PDFs have no OCR.

With conversations saved, enable **Study mode**. Right-click, long-press or choose **Save to notes** on a message. Search saved passages and comments in the notes panel; highlight, bold, comment, return to the original message, or move a note to Trash and restore it. Notes participate in the existing memory system.

## Bring existing conversations

Use the original platform's official export first. Stet does not sign into those accounts.

| Export | Supported content | Boundaries |
|---|---|---|
| ChatGPT `conversations.json` or ZIP containing it | Parent-linked message graph, roles, text, timestamps, available model metadata | Separate leaf branches; shared prefixes can appear in multiple branches |
| Claude `conversations.json` or ZIP | `chat_messages`, human/assistant roles, text blocks and creation times | Missing dates/branches stay unknown; attachments are reported, not imported |
| Gemini Takeout `MyActivity.json` or ZIP | Gemini Apps/Bard activity titles and timestamps | May contain prompts only. No invented replies or conversation grouping. Choose JSON; HTML is unsupported |
| AI Studio JSON | `chunkedPrompt.chunks` text and user/model roles | Not a Gemini App backup. Missing IDs use content identity; updated files may become separate sources |
| Stet / legacy Continuity JSON or Markdown | Explicit message metadata | Legacy `Continuity transcript v1` remains accepted; arbitrary Markdown is not guessed |

Maximum 32 MiB per file, 20,000 expanded records. ZIP import selects exactly one recognized conversation JSON, never extracts files to disk, and ignores other attachments. If ambiguous, unzip manually and select one JSON. Split larger exports by complete conversations, preserving graph references.

Review the preview and omission report before confirming. Only the first 200 records are displayed, but totals and validation cover all records. Non-text content is not searchable. Unsupported formats fail explicitly. Original bytes remain downloadable via **View source**. Duplicate files are idempotent; conflicting records are not overwritten. **Remove import batch** deletes this app's stored copy and batch-exclusive messages, not your external originals or backups.

## Connect and chat

**Models & connections**: save your own Gemini or DeepSeek key, enable paid requests and save settings. Never paste keys into chat. The GPT subscription bridge is not configured in this preview.

**Generation & memory**: control source text allowance, Gemini reasoning/output and automatic corrections. **Agent & preferences**: define your own agent name, relationship and interaction preferences. **Web tools**: optionally connect Tavily and enable search. **Usage & limits**: observe estimates and optional spending gates. Price entries are dated snapshots, not guaranteed current rates. Currency stays CNY when switching to English; USD provider rates use your chosen exchange rate. There are no automatic purchases or subscriptions.

Choose a model in Chat, then send. Connection checks test model-information access, not generation. Requests may include the current message, selected history, sources and attachments. Local search and note collection do not call paid models.

## Preview boundaries

**Video (Beta)** offers local camera/microphone preview and explicit call start. Real devices, networks and provider support require testing. Raw audio/video is not stored; confirmed transcripts and observations can enter memory. Leaving the page, backgrounding or locking ends a call. No cloned voice is bundled. Studio is hidden for now.

Default hosting is loopback-only: your phone cannot reach your computer's `127.0.0.1`. Remote access requires separate authentication and HTTPS setup. Browser installation is a shortcut, not an always-on backend.

The Memory-R2-inspired trained policy and layered persona architecture are **proposals**, not shipped models or proven personality stability. Report reproducible steps and version information without secrets or private archives.

[中文指南](14-getting-started.md) · [Engineering proposal (Chinese with English summary)](16-memory-persona-design.md)
