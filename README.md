# Multi-Agent Orchestration Demo

> **Claude Code (ACP) + OpenHands** — multiple agent harnesses orchestrated
> from one platform, running on OpenHands Cloud.

## What This Does

OpenHands orchestrates **different AI coding agents** working together on one task:

| Step | Harness | Protocol | What happens |
|------|---------|----------|--------------|
| **Implement** | **Claude Code** | ACP (Agent Client Protocol) | Claude Code writes the code via real ACP |
| **Review** | **OpenHands** | SDK delegation | File-based reviewer agent finds issues |
| **Fix** | **OpenHands** | SDK delegation | Implementer fixes MAJOR/CRITICAL findings |

## Quick Start

### Prerequisites

1. **OpenHands Cloud API Key** — [app.all-hands.dev](https://app.all-hands.dev) → Settings → API Keys
2. **Anthropic API Key** — add as a secret in OpenHands Cloud: Settings → Secrets → `ANTHROPIC_API_KEY`

### Run it

```bash
git clone https://github.com/rajshah4/openhands-multi-agent-demo.git
cd openhands-multi-agent-demo

pip install requests

export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"

python demo.py
```

That's it. This starts a Cloud conversation that:

1. Provisions a sandbox
2. Installs the OpenHands SDK + Claude Code ACP server
3. Runs `pipeline.py` using **real ACP** to talk to Claude Code
4. Claude Code writes the code, OpenHands reviews + fixes it

Watch it live at the URL printed in the output.

### Options

```bash
python demo.py                          # default: url-shortener task
python demo.py --task csv-tool          # CSV-to-JSON converter
python demo.py --task custom --custom-task "Build a rate limiter"
python demo.py --repo youruser/yourrepo # use your own repo
python demo.py --no-claude              # OpenHands only (no ACP)
```

## Architecture

```
Your laptop                        OpenHands Cloud
┌──────────┐                       ┌──────────────────────────────────┐
│ demo.py  │── Cloud API ────────► │  Sandbox                         │
│          │                       │  ┌──────────────────────────────┐ │
│  starts  │   visible in UI       │  │ pipeline.py (orchestrator)   │ │
│  convo   │◄─ at app.all-hands ── │  │                              │ │
│          │                       │  │  ┌─────────┐  ┌───────────┐  │ │
└──────────┘                       │  │  │ Claude  │  │ OpenHands │  │ │
                                   │  │  │ Code    │  │ Reviewer  │  │ │
                                   │  │  │ (ACP)   │  │ (.md)     │  │ │
                                   │  │  └─────────┘  └───────────┘  │ │
                                   │  └──────────────────────────────┘ │
                                   └──────────────────────────────────┘
```

`ACPAgent` spawns Claude Code as an ACP server subprocess inside the sandbox.
Communication happens via **JSON-RPC 2.0 over stdio** — the same protocol IDEs
use to talk to AI agents. This is real ACP, not a CLI wrapper.

## Files

| File | Role |
|------|------|
| `demo.py` | **Entry point** — starts the Cloud conversation |
| `pipeline.py` | **ACP pipeline** — runs inside the sandbox, orchestrates Claude Code + OpenHands |
| `.agents/agents/code-reviewer.md` | **File-based agent** — code reviewer defined in Markdown |

## Enterprise Value

- **Multi-harness** — Claude Code writes, OpenHands reviews. Best of both worlds.
- **Real ACP** — Agent Client Protocol, not CLI shelling. Proper agent-to-agent communication.
- **Observable** — Full pipeline visible in OpenHands Cloud UI
- **Vendor-flexible** — Swap Claude Code for any ACP-compatible agent
- **Extensible** — Add agents as Markdown files, no deployment needed
