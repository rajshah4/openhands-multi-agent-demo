# Multi-Agent Orchestration Patterns for OpenHands

Runnable patterns for coordinating multiple OpenHands agents. The first
decision is the orchestrator's lifetime: do you want a **constantly running
orchestrator** that drives a task from start to finish (best for short to
medium tasks), or a **polling orchestrator** that wakes on a schedule, nudges
the work forward, and exits (best for long-running work)? A third pattern
drops the orchestrator entirely and lets **events** advance the work.

The distinction that matters: **the parent-child orchestrator waits for its
workers; the polling orchestrator never waits — it checks back later.**

| | [Pattern 1: Parent-Child](patterns/parent-child/) | [Pattern 2: Polling Loop](patterns/polling/) |
| --- | --- | --- |
| One line | Run a full lifecycle of child agents, **now** | Keep a backlog moving, **forever** |
| Who advances the work | A live parent that stays up for the whole run | A scheduled tick that exits after one action |
| Shape | Parent delegates plan -> build -> check children and gates on each | Wake, observe state, take one action, exit |
| Memory | The live orchestrator + a run directory | Durable state on disk (or labels/tickets) - no live process |
| Use when | One request should produce one complete, visible result | Work spans hours/days and must survive crashes and restarts |
| Production example | [sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo) (Jira ticket -> PR + review + QA) | [ohtv-workflow](https://github.com/jpshackelford/.openhands/tree/main/plugins/ohtv-workflow) (issue-to-merge on cron) |

![Parent-child pattern: a live parent starts children in order and gates on each status report](assets/pattern-parent-child.svg)

![Polling loop pattern: a scheduled tick reads durable state, takes one action, and exits](assets/pattern-polling.svg)

Both patterns run locally in Agent Canvas or on OpenHands Enterprise/Cloud.
The isolation model differs: Enterprise gives every worker conversation its
own sandbox; Agent Canvas conversations run on your machine, where they can
share a working directory (what this demo does) or attach a git repository
with a separate git worktree per conversation.

## Quickstart

This section has a runnable example of each approach. Against OpenHands
Cloud, Enterprise, or self-hosted - same API:

```bash
export OPENHANDS_API_KEY="your-key"
# export OPENHANDS_BASE_URL="https://openhands.your-company.com"   # if not app.all-hands.dev
```

Using local Agent Canvas instead? Skip the export: add `--runtime canvas` to
either script. The scripts find your local Canvas automatically - the key is
read from `~/.openhands/agent-canvas/api-key.txt` and the API is
`http://localhost:8000` - and every worker appears as a live conversation in
the Canvas UI.

**Pattern 1 - Parent-Child.** One command runs a three-cell lifecycle with
real child conversations and writes a lifecycle report:

```bash
cd patterns/parent-child
python3 run_supervisor.py --request "a Python function slugify(text) for URL-safe slugs"
cat runs/*/lifecycle-report.md
```

**Pattern 2 - Polling Loop.** Each command is one tick; run it repeatedly and
watch the state machine advance through a seeded backlog:

```bash
cd patterns/polling
python3 orchestrate_once.py   # claims task-1, spawns a real worker, exits
python3 orchestrate_once.py   # worker still running -> quiet tick
python3 orchestrate_once.py   # worker done -> records result, next tick claims task-2
cat WORKLOG.md
```

The demo tasks are very small to highlight the pattern. You can run a real
software factory built on the same shapes in
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo).

## The Ideas Underneath

Three transferable ideas carry both patterns:

1. **Small status reports, not shared context.** Each worker gets a
   self-contained prompt and ends its reply with a short, fixed-format status
   report (`status:` / `summary:` / `next_gate:`). The orchestrator decides
   what happens next by reading those few lines alone - it never has to dig
   through everything the worker did.

2. **State placement is the design decision.** The parent-child orchestrator
   holds state in a live process. The polling loop holds it in durable
   records. Everything else - crash recovery, cost profile, time horizon -
   follows from that choice.

3. **Humans own the irreversible.** Workers never merge, deploy, or approve
   their own output - they do bounded work and report back. The orchestrator
   is the control point: the parent stops the lifecycle when a child reports
   `needs-human`, and the polling loop pauses whenever a human writes into
   `INSTRUCTIONS.md`. Final approval for irreversible actions stays with
   people.

## Pattern 3: Event-Driven Handoff

The first two patterns keep an orchestrator - live or scheduled. The third
removes it: each agent finishes by changing the **system of record** - pushing
a branch, adding a label, updating a ticket - and that change triggers the
next agent through an automation or webhook. Nothing orchestrates; events
advance the work.

![Event-driven handoff: each finished step changes the system of record, which triggers the next agent](assets/pattern-event-driven.svg)

| Pattern | Who advances the work |
| --- | --- |
| Parent-child | A live parent |
| Polling loop | A scheduled tick |
| Event-driven handoff | The event itself - no orchestrator |

The production example is the step-by-step path in
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo):
a human applies a GitHub label (`openhands-build`, `openhands-review`,
`openhands-qa`), each label triggers one bounded automation, and the results
land back on the issue or PR. The system of record is the workflow.

This repo's original demos show three **handoff mediums** on the same
implement -> test -> review pipeline, from tightest to loosest coupling:

| Script | Handoff medium | Notable |
| --- | --- | --- |
| [`shared_workspace.py`](shared_workspace.py) | One shared workspace - agents hand off through the filesystem | Multi-agent AND multi-harness: Claude Code implements, Gemini CLI tests, OpenHands reviews, via ACP |
| [`multi_server_isolation.py`](multi_server_isolation.py) | Git - each agent works in an isolated clone and pushes; the push is the handoff | The git artifact is the trigger; swap the driving script for webhooks and it becomes fully event-driven |
| [`cloud_conversations.py`](cloud_conversations.py) | Managed Enterprise conversations chained by API | One sandbox per phase with a web UI; replace the script with automations for a no-orchestrator chain |

Run them:

```bash
# Shared workspace (SDK + ACP; three harnesses, one filesystem)
pip install openhands-sdk openhands-tools
export LLM_API_KEY="..." ANTHROPIC_API_KEY="..." GEMINI_API_KEY="..."
python shared_workspace.py               # or --no-claude for pure OpenHands delegation

# Isolated local clones (manual git orchestration, local pytest verification)
pip install openhands-ai pytest
python multi_server_isolation.py         # or --task csv-tool

# Cloud/Enterprise conversations (one sandbox per phase)
pip install requests
export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"
python cloud_conversations.py            # or --repo youruser/yourrepo
```

📖 [`PATTERNS.md`](PATTERNS.md) is the deep dive on these three runtime
setups: isolation vs. complexity trade-offs, decision trees, and migration
paths.

## Multi-Harness, ACP, and Agent Canvas

The workers in any of these patterns do not have to be OpenHands-native
agents, and you do not have to pick one harness for everything:

- **OpenHands Enterprise** runs each worker in its own conversation and
  sandbox, so different phases can use different models or harnesses without
  touching each other.
- **ACP (Agent Client Protocol)** lets a worker slot be filled by an outside
  harness such as Claude Code or Gemini CLI: the OpenHands SDK's `ACPAgent`
  wraps any ACP-speaking tool as a first-class agent. The working example is
  [`shared_workspace.py`](shared_workspace.py) - three vendors, one control
  plane.
- **Agent Canvas** runs both patterns locally (`--runtime canvas`) and shows
  every worker as a live conversation you can open while it runs. Canvas and
  Enterprise expose different APIs (local conversations vs app-conversations
  with start tasks); this repo ships one backend for each with the same
  function surface, so the pattern scripts run on both unchanged.

Details and code: [Agent Canvas and ACP](docs/agent-canvas-and-acp.md).

## Repo Map

```text
patterns/
  common/openhands_conversations.py   # Cloud/Enterprise backend (app-conversations API)
  common/canvas_conversations.py      # local Agent Canvas backend (same surface)
  parent-child/                       # Pattern 1: run_supervisor.py + prompts + README
  polling/                            # Pattern 2: orchestrate_once.py + backlog + README
docs/
  choosing-a-pattern.md               # the decision guide + composition + state model
  agent-canvas-and-acp.md             # Canvas as visible runtime, ACP for harness mixing
tests/                                # contract tests; run offline: python3 -m pytest -q
```

## Links

- [OpenHands Cloud](https://app.all-hands.dev) - run and observe agent conversations
- [OpenHands SDK docs](https://docs.openhands.dev/sdk/overview) - build agent pipelines in Python
- [Agent Client Protocol (ACP)](https://docs.agentclientprotocol.com/) - the protocol connecting harnesses
