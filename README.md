# Multi-Agent Orchestration Patterns for OpenHands

Runnable patterns for coordinating multiple OpenHands agents. Three ways to
build an agent workflow, split by one question - **who advances the work?**

- **Parent-Child:** a constantly running orchestrator drives a task from start
  to finish. It *waits* for each worker. Best for short-to-medium tasks.
- **Polling Loop:** a scheduled orchestrator wakes, nudges the work forward,
  and exits. It *never waits* - it checks back on the next tick. Best for
  long-running work.
- **Event-Driven Handoff:** no orchestrator at all. Each finished step changes
  the system of record, and *that change triggers* the next agent. Best when
  the workflow already lives in GitHub or Jira.

| | [Pattern 1: Parent-Child](patterns/parent-child/) | [Pattern 2: Polling Loop](patterns/polling/) | Pattern 3: Event-Driven Handoff |
| --- | --- | --- | --- |
| One line | Run a full lifecycle of child agents, **now** | Keep a backlog moving, **forever** | Let the system of record drive the work |
| Who advances the work | A live parent that stays up for the whole run | A scheduled tick that exits after one action | The event itself - no orchestrator |
| Shape | Parent delegates plan -> build -> check children and gates on each | Wake, observe state, take one action, exit | Agent finishes -> label/push/ticket change -> automation triggers the next agent |
| Memory | The live orchestrator + a run directory | Durable state on disk (or labels/tickets) - no live process | The system of record itself |
| Use when | One request should produce one complete, visible result | Work spans hours/days and must survive crashes and restarts | Every step has a natural trigger and humans gate between steps |
| Production example | [sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo) (Jira ticket -> PR + review + QA) | [ohtv-workflow](https://github.com/jpshackelford/.openhands/tree/main/plugins/ohtv-workflow) (issue-to-merge on cron) | [sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo) step-by-step labels |

![Parent-child pattern: every child reports back to the parent; children never talk to each other](assets/pattern-parent-child.svg)

![Polling loop pattern: a scheduled circle of work - wake, check state, decide, take one action, log and exit](assets/pattern-polling.svg)

Both patterns run locally in Agent Canvas or on OpenHands Enterprise/Cloud.
The isolation model differs: Enterprise gives every worker conversation its
own sandbox; Agent Canvas conversations run on your machine, where they can
share a working directory (what this demo does) or attach a git repository
with a separate git worktree per conversation.

## Quickstart

This section has a runnable example of the first two patterns - the ones with
an orchestrator to run. (Pattern 3 has no orchestrator; its triggers live in
GitHub/Jira - see [its section](#pattern-3-event-driven-handoff).) Against
OpenHands Cloud, Enterprise, or self-hosted - same API:

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

Three transferable ideas carry all three patterns:

1. **Small status reports, not shared context.** Each worker gets a
   self-contained prompt and ends its reply with a short, fixed-format status
   report (`status:` / `summary:` / `next_gate:`). The orchestrator decides
   what happens next by reading those few lines alone - it never has to dig
   through everything the worker did.

2. **State placement is the design decision.** The parent-child orchestrator
   holds state in a live process. The polling loop holds it in durable
   records. Event-driven handoff goes all the way: state lives entirely in
   the system of record. Everything else - crash recovery, cost profile,
   time horizon - follows from that choice.

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

The production example is the step-by-step path in
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo):
a human applies a GitHub label (`openhands-build`, `openhands-review`,
`openhands-qa`), each label triggers one bounded automation, and the results
land back on the issue or PR. The system of record is the workflow.

### Where the Original Demos Fit

This repo predates the pattern framing with three linear
implement -> test -> review demos. Here is how each maps onto the patterns -
and what it becomes if you grow it up:

| Original demo | Which pattern is it? | What it grows into |
| --- | --- | --- |
| [`cloud_conversations.py`](cloud_conversations.py) | **Parent-child, simplified.** The script is a live parent that starts each Enterprise conversation and waits for it - just without gates. | Pattern 1 is its upgrade: add status reports and gate logic and you have `run_supervisor.py`. |
| [`multi_server_isolation.py`](multi_server_isolation.py) | **Parent-child today, event-driven in spirit.** The script still waits on each phase, but the handoff artifact is a git push - exactly the kind of event automations trigger on. | Remove the waiting script and let automations react to the pushes/labels instead: that is Pattern 3, and the sdlc label demo is precisely that, in production. |
| [`shared_workspace.py`](shared_workspace.py) | **Not an orchestration pattern - a runtime + harness choice.** Agents relay work inside one shared workspace, each picking up the previous agent's files. The sequencing is still done by a waiting script (parent-child shape). | Keep it as the **multi-harness proof**: Claude Code implements, Gemini CLI tests, OpenHands reviews, connected by ACP. Any of the three patterns can use this - a shared workspace and ACP workers are choices about *where workers run* and *what fills the worker slot*, not about who advances the work. |

Is the shared-workspace relay a real use case? Yes, but a narrow one: tight
sequential collaboration on one checkout (no re-cloning, no artifact passing)
where isolation between agents does not matter. You can do the same thing in
Agent Canvas with ACP-backed conversations sharing a working directory. Its
lasting value here is proving the worker slot is harness-agnostic - the
orchestration question is still answered by one of the three patterns above.

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
