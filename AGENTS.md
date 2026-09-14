# AGENTS.md — openhands-multi-agent-demo

Practical examples of coordinating multiple OpenHands agents across three orthogonal decisions: where agents run (execution), who decides what happens next (coordination), and where workflow state survives (durable state).

## Repository Overview

Three orchestration patterns are demonstrated:

| Pattern | Entry point | When to use |
|---|---|---|
| SDK subagents + ACP | `shared_workspace.py` | Bounded specialist delegation inside one shared runtime |
| Automations / reconciliation | `patterns/polling/orchestrate_once.py` | Ongoing backlog; work that spans hours or days |
| Parent-child conversations | `patterns/parent-child/run_supervisor.py` | One bounded request needing separate audit records and human gates |

## Quick Commands

```bash
# Install
pip install openhands-ai pytest

# Dry-run (no API key needed)
python3 patterns/polling/orchestrate_once.py --dry-run
python3 patterns/parent-child/run_supervisor.py --dry-run

# Run tests (offline)
pytest tests/ -v

# Real runs
export OPENHANDS_API_KEY="your-key"
python3 patterns/polling/orchestrate_once.py
python3 patterns/parent-child/run_supervisor.py --request "your task"
python3 shared_workspace.py
```

## Key Files

- `shared_workspace.py` — SDK subagents and ACP workers (Claude Code, Gemini CLI, OpenHands)
- `cloud_conversations.py` — coding harnesses in separate managed cloud conversations
- `multi_server_isolation.py` — fully isolated local clones exchanging via git
- `patterns/polling/` — restartable reconciliation loop
- `patterns/parent-child/` — live supervisor with gated child conversations
- `patterns/common/` — Enterprise and Canvas conversation adapters
- `automations/implement-approved-spec/` — event-driven label → implement-spec → PR automation
- `BEST_PRACTICES.md` — full operating guidance (state, capacity, validation, recovery, cleanup)
- `docs/choosing-a-pattern.md` — decision guide: parent-child vs polling vs event-driven
- `docs/agent-canvas-and-acp.md` — Agent Canvas runtime and ACP worker details
- `.agents/skills/orchestrate-multi-agent-conversations/` — reusable orchestration skill

## Runtime Flags

Both pattern scripts accept `--runtime canvas` to run on local Agent Canvas instead of Cloud/Enterprise, and `--dry-run` to preview without any API calls.

---

## Autodocs

- **Wiki:** [`openwiki/`](openwiki/)
- **Last updated:** 2026-08-31 (source commit `da74194`)
- **Maintained by:** [Autodocs](https://github.com/OpenHands/extensions) — edit `openwiki/` pages directly; update `.last-update.json` when source changes are documented.
