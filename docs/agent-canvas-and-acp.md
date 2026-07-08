# Agent Canvas and ACP

The two patterns in this repo are deliberately harness-agnostic: an
orchestrator needs exactly two things from a worker - *start it with a
self-contained prompt* and *learn its outcome*. Anything with those two
properties can fill a worker slot. This page covers the two pieces that make
that concrete: **Agent Canvas** (where the patterns become visible) and **ACP**
(how non-OpenHands harnesses plug in).

## Agent Canvas: The Visible Runtime

Agent Canvas is the local, visual surface over the OpenHands Agent Server.
Every conversation is a node you can open, and a parent delegating children
stops being an abstract diagram - you watch the supervisor spawn its
plan/build/check children as separate live conversations.

Both pattern scripts run on Canvas with a flag - no code changes:

```bash
# local Agent Canvas running at localhost:8000
python3 patterns/parent-child/run_supervisor.py --runtime canvas
python3 patterns/polling/orchestrate_once.py --runtime canvas
```

Every child/worker appears as its own conversation in the Canvas UI, openable
mid-run. The sdlc repo's
[Agent Canvas recipe](https://github.com/rajshah4/sdlc-automation-github-demo/tree/main/agent-canvas)
is the grown-up version: a parent Canvas conversation runs the orchestrator
itself, and story-to-pr / code-review / qa children appear as delegated
conversations.

## Two Runtimes, Two APIs, One Pattern

The `--runtime` flag exists because Canvas and Cloud/Enterprise expose
genuinely different APIs. The pattern scripts never notice - both backends in
`patterns/common/` expose the same
`build_start_payload / start_worker / get_status / get_final` surface:

| | Cloud/Enterprise (`openhands_conversations.py`) | Agent Canvas (`canvas_conversations.py`) |
| --- | --- | --- |
| Create | `POST /api/v1/app-conversations` -> start task -> poll for conversation id | `POST /api/conversations` -> id immediately |
| Auth | `Authorization: Bearer <api key>` | `X-Session-API-Key` from `~/.openhands/agent-canvas/api-key.txt` |
| Settings | Held server-side in the secret store | Client round-trips encrypted settings (`X-Expose-Secrets: encrypted` + `secrets_encrypted: true`) |
| Final response | Reconstructed from the events search | Dedicated `GET .../agent_final_response` endpoint |
| Worker state | Isolated sandbox per conversation | Shared local working tree (`worktree: false`) |

The last row is the one that changes behavior, not just plumbing: on Canvas,
workers run on your machine. This demo points them at a shared scratch
directory (inside the gitignored run/results area), so files transfer
directly between cells but runs are not parallel-safe. When a Canvas
conversation attaches a git repository, it can instead use a separate git
worktree per conversation for isolation.
See [the state question](choosing-a-pattern.md#the-state-question-where-worker-output-goes).

## ACP: Any Harness in the Worker Slot

[ACP (Agent Client Protocol)](https://docs.agentclientprotocol.com/) is a
standard protocol for driving agent harnesses as subprocesses. The OpenHands
SDK ships an `ACPAgent` that wraps any ACP-speaking harness as a first-class
agent:

```python
from openhands.sdk.agent import ACPAgent

claude_code = ACPAgent(
    acp_command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
    acp_env={"ANTHROPIC_API_KEY": anthropic_key},
)

gemini_cli = ACPAgent(
    acp_command=["gemini", "--acp"],
    acp_env={"GEMINI_API_KEY": gemini_key},
)
```

The working proof lives in this repo:
[`shared_workspace.py`](../shared_workspace.py) runs one pipeline where Claude
Code implements, Gemini CLI writes tests, and OpenHands reviews - three
vendors, two ACP harnesses, one control plane.

Because Agent Canvas runs on the same Agent Server / SDK line, ACP is how
Canvas gets harness plurality built in: a Canvas conversation node does not
have to be an OpenHands-native agent. The composition becomes visual - a
supervisor node delegating to a Claude Code node and a Gemini node, each
inspectable on the canvas.

## What This Means for the Patterns

The orchestrator's contract never mentions a harness:

```text
start(worker_prompt) -> outcome (final response or state change)
```

So the harness decision collapses to a per-worker-slot choice:

| Worker slot filled by | How | When |
| --- | --- | --- |
| OpenHands conversation (default) | `patterns/common/openhands_conversations.py` | Full sandbox, repo access, skills, the managed path |
| Local Canvas conversation | `patterns/common/canvas_conversations.py` (`--runtime canvas`) | Demos and development where seeing the graph matters |
| ACP harness (Claude Code, Gemini CLI, ...) | `ACPAgent` via the SDK | A specific harness is best-in-class for one cell, or the team already lives in it |

Swap one worker without touching the pattern. That is the actual value of
harness flexibility - not that you *must* mix vendors, but that the workflow
shape survives when you do.
