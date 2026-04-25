# Multi-Agent Orchestration Demo

> **Claude Code + Gemini CLI + OpenHands** — three vendors, two ACP harnesses,
> one control plane. Running on OpenHands Cloud.

## What This Does

OpenHands orchestrates **three different AI coding agents** working together:

| Phase | Harness | Vendor | Protocol | Task |
|-------|---------|--------|----------|------|
| 1 | **Claude Code** | Anthropic | ACP | Writes the implementation |
| 2 | **Gemini CLI** | Google | ACP | Writes the tests |
| 3 | **OpenHands** | OpenHands | SDK | Reviews everything |

## Quick Start

### Prerequisites

Add these as **secrets** in [OpenHands Cloud](https://app.all-hands.dev) → Settings → Secrets:
- `ANTHROPIC_API_KEY` — for Claude Code ([console.anthropic.com](https://console.anthropic.com))
- `GEMINI_API_KEY` — for Gemini CLI ([aistudio.google.com](https://aistudio.google.com/apikey))

Get a **Cloud API Key** from Settings → API Keys.

### Run it

```bash
git clone https://github.com/rajshah4/openhands-multi-agent-demo.git
cd openhands-multi-agent-demo

pip install requests

export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"

python demo.py
```

Watch it live at the URL printed in the output.

### Options

```bash
python demo.py                          # default: url-shortener
python demo.py --task csv-tool          # CSV-to-JSON converter
python demo.py --task custom --custom-task "Build a rate limiter"
python demo.py --repo youruser/yourrepo # your own repo
python demo.py --no-claude              # OpenHands only (no ACP)
```

## Architecture

```
Your laptop                        OpenHands Cloud Sandbox
┌──────────┐                       ┌────────────────────────────────┐
│ demo.py  │── Cloud API ────────► │  pipeline.py (orchestrator)    │
│          │                       │                                │
│  starts  │   visible in UI       │  Phase 1: Claude Code (ACP)   │
│  convo   │◄─ at app.all-hands ── │    └─ writes shortener.py     │
│          │                       │                                │
└──────────┘                       │  Phase 2: Gemini CLI (ACP)    │
                                   │    └─ writes test_shortener.py │
                                   │                                │
                                   │  Phase 3: OpenHands            │
                                   │    └─ reviews all .py files    │
                                   └────────────────────────────────┘
```

Both ACP harnesses communicate via **JSON-RPC 2.0 over stdio** — the same
protocol IDEs use to talk to AI agents. Real ACP, not CLI wrappers.

## Files

| File | Role |
|------|------|
| `demo.py` | **Run this** — starts the Cloud conversation |
| `pipeline.py` | ACP pipeline — runs inside the sandbox |
| `.agents/agents/code-reviewer.md` | File-based reviewer agent (Markdown) |

## Enterprise Value

- **Multi-vendor** — Anthropic writes, Google tests, OpenHands reviews
- **Real ACP** — Agent Client Protocol, proper agent-to-agent communication
- **Observable** — Full pipeline visible in OpenHands Cloud UI
- **Vendor-flexible** — Swap any ACP agent without changing the pipeline
- **Extensible** — Add agents as Markdown files, no deployment needed
