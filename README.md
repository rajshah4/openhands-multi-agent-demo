# Multi-Agent Orchestration Demo

> **Claude Code + Gemini CLI + OpenHands** — three vendors, three conversations,
> one repo. Running on OpenHands Cloud.

![OpenHands Multi-Agent Demo — three conversations, three vendors, one repo](assets/multi-conversation.png)

## What This Does

OpenHands orchestrates **three different AI coding agents**, each in its own
Cloud conversation, communicating through the git repo:

| Phase | Harness | Vendor | Conversation | Task |
|-------|---------|--------|--------------|------|
| 1 | **Claude Code** | Anthropic | ☁️ Own sandbox | Writes the implementation, commits to repo |
| 2 | **Gemini CLI** | Google | ☁️ Own sandbox | Pulls code, writes tests, commits to repo |
| 3 | **OpenHands** | OpenHands | ☁️ Own sandbox | Pulls everything, reviews all code |

Each conversation is independently visible in the [Cloud UI](https://app.all-hands.dev).
The repo is the communication channel — just like real engineering teams.

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

You'll see three conversation URLs — click each one to watch that agent work live.

### Options

```bash
python demo.py                          # default: url-shortener
python demo.py --task csv-tool          # CSV-to-JSON converter
python demo.py --task custom --custom-task "Build a rate limiter"
python demo.py --repo youruser/yourrepo # your own repo
python demo.py --no-claude              # OpenHands for all steps
```

## Architecture

```
demo.py (your laptop)
│
├─► ☁️ Conversation 1   [Claude Code / Anthropic]
│     └─ installs Claude Code, implements shortener.py, pushes to repo
│
├─► ☁️ Conversation 2   [Gemini CLI / Google]
│     └─ installs Gemini CLI, pulls repo, writes test_shortener.py, pushes
│
└─► ☁️ Conversation 3   [OpenHands]
      └─ pulls repo, reviews all .py files, reports findings
```

Each conversation gets its own sandbox. Agents communicate through the
shared git repo — Claude Code pushes code, Gemini CLI pulls it and adds
tests, OpenHands pulls everything and reviews.

## Demo Results

Actual output from a run on OpenHands Cloud (April 2026):

| Phase | Harness | Cost | Output |
|-------|---------|------|--------|
| Implement | Claude Code | $0.048 | `shortener.py` — URL shortener with `shorten()`, `resolve()`, `stats()` |
| Write Tests | Gemini CLI | $0.000 | `test_shortener.py` + additional test files — 17 pytest tests |
| Review | OpenHands | $0.338 | 12 findings including command injection vuln and hash collision bug |
| **Total** | **3 vendors** | **$0.39** | |

## Alternative: ACP Subprocess Mode

For direct agent-to-agent communication via ACP (Agent Client Protocol),
use `pipeline.py`. This runs all harnesses as subprocesses in a single
sandbox, communicating via JSON-RPC 2.0 over stdio:

![OpenHands Agent Control Plane — ACP architecture](assets/architecture.png)

```bash
# Requires openhands-sdk — runs locally or inside a Cloud sandbox
pip install openhands-sdk openhands-tools
export LLM_API_KEY="your-key" ANTHROPIC_API_KEY="your-key" GEMINI_API_KEY="your-key"
python pipeline.py
```

## Files

| File | Role |
|------|------|
| `demo.py` | **★ Run this** — orchestrates three Cloud conversations |
| `pipeline.py` | Alternative: ACP subprocess pipeline (single sandbox) |
| `.agents/agents/code-reviewer.md` | File-based reviewer agent (Markdown, used by pipeline.py) |

## Enterprise Value

- **Multi-vendor** — Anthropic implements, Google tests, OpenHands reviews
- **Observable** — Each agent in its own conversation, fully auditable in Cloud UI
- **Distributed** — Agents communicate through artifacts (git), not tight coupling
- **Vendor-flexible** — Swap any agent without changing the pipeline
- **Extensible** — Add new harnesses by adding entries to `HARNESS_INSTRUCTIONS`
- **Cost-effective** — Full implement + test + review pipeline for under $0.40
