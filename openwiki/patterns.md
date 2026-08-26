# Orchestration Patterns

Four ways to advance multi-agent work. Choose based on two questions:

1. **Is the work one bounded request or an ongoing backlog?** A single request that should finish while someone watches → parent-child. A refilling backlog where work waits on slow externals → reconciliation loop.
2. **Can anything hold state for the full duration?** If a single conversation or process can stay alive for the whole job → parent-child. If the job spans hours or days → durable state + reconciliation.

The patterns compose. A polling loop's worker can be an entire parent-child lifecycle. A parent-child child can use SDK subagents internally.

---

## 1. SDK Orchestration (shared workspace)

**Shape:** your Python application is the controller. It starts subagents, passes assignments, waits for results, validates them, and decides when to stop.

**Use when:** one bounded task needs a few researchers, reviewers, test planners, or other specialists that can safely share a runtime and failure scope.

```
application
  → implementer subagent (TaskToolSet)
  → tester subagent
  → reviewer subagent
  → result
```

The parent and all subagents share one filesystem, credential set, timeout, and failure scope. Keep queue ownership outside subagent calls. Use first-class child conversations when workers need separate audit records, independently chosen runtimes, or stronger isolation.

**Working example:** [`shared_workspace.py`](../shared_workspace.py)

The same file demonstrates ACP workers: Claude Code implements, Gemini CLI tests, OpenHands reviews — three vendors, two ACP harnesses, one control plane.

---

## 2. Automations and Reconciliation (polling loop)

**Shape:** a schedule or event starts a temporary controller. The controller reloads durable state, compares desired and actual progress, takes one bounded action, records what happened, and exits. A later run continues from the checkpoint.

**Use when:** work arrives continuously, spans hours or days, waits on CI or human review, or naturally advances through GitHub, Jira, or another system of record.

```
wake → read state → decide → (spawn | record | quiet) → checkpoint → exit
  ↑                                                                    |
  '─────────────────────── next tick ──────────────────────────────────'
```

**Four ideas that make it work:**

1. The orchestrator is stateless; the state is durable. A tick reads state, acts, writes a checkpoint, and exits.
2. Fire and forget. A tick that spawns a worker does not wait for it. Observing the worker is the next tick's job.
3. One action per tick. Claim one task, record one result, or stay quiet.
4. Humans pause the loop with a file. Write anything into `INSTRUCTIONS.md` and the next tick does nothing until the file is cleared.

**Working example:** [`patterns/polling/`](../patterns/polling/)

Run ticks by hand:

```bash
cd patterns/polling
python3 orchestrate_once.py --dry-run     # preview without API calls
python3 orchestrate_once.py               # real tick
python3 orchestrate_once.py --reset       # clear state and start over
```

The teaching example uses local files. Production automations running in ephemeral infrastructure should use automation KV, GitHub, Jira, or an application database.

---

## 3. Parent-Child Conversations

**Shape:** a live parent owns one bounded request. It breaks the request into focused assignments, starts first-class worker conversations, validates their output contracts, applies gates, and writes a lifecycle report.

**Use when:** workers need separate histories, visible conversation links, clean execution environments, different credentials, or human checkpoints between stages — and one parent can remain active for the bounded lifecycle.

```
request
  → live parent
    → implementation child
    → code-review child
    → QA child
  → lifecycle report
  → human decides
```

Each child receives one responsibility and a small result contract. A blocking review, malformed output, missing final response, or timeout becomes `needs-human` — it is not silently inferred as success.

Workers exchange code through durable branches or pull requests, not by assuming local files are visible to one another. Sandbox placement follows the deployment's grouping configuration; when explicit isolation is required, the controller must create the sandbox explicitly.

**Working example:** [`patterns/parent-child/`](../patterns/parent-child/)

```bash
cd patterns/parent-child
python3 run_supervisor.py --dry-run
python3 run_supervisor.py --request "a Python slugify(text) function"
```

Output appears in `runs/<run-id>/`: prompt, final response, and lifecycle report for each child.

---

## 4. Event-Driven Handoff (no persistent orchestrator)

**Shape:** each agent finishes by changing the system of record — a push, a label, a ticket transition — and that change triggers the next agent through an automation or webhook. No orchestrator stays alive between stages.

**Use when:** the workflow is already expressed in a system of record and every step has a natural external trigger.

```
Jira story ready
  → implementation automation → agent opens PR
  → PR opened event → independent review agent
  → review passed → QA agent
  → status back to Jira and GitHub
  → human decides whether to merge
```

The agents do not communicate directly. Jira, GitHub, the branch, the PR, and the validation results provide the handoffs and the durable record. Retries remain safe when every stage records stable identifiers and checks whether the intended action already happened.

**Working example:** [`automations/implement-approved-spec/`](../automations/implement-approved-spec/) — adding the label `openhands-implement-spec` to a GitHub issue starts the implement-spec skill, which produces a PR for human review.

The [SDLC Automation Demo](https://github.com/rajshah4/sdlc-automation-github-demo) contains the full GitHub-native version of this build → review → QA pipeline.

---

## Composing the Patterns

```
scheduled reconciliation tick (pattern 2)
  → observes ticket KAN-42 is ready
  → starts one bounded parent-child lifecycle (pattern 3)
      → implementation conversation
      → review conversation
      → QA conversation
      → lifecycle report
  → exits

next tick observes the lifecycle result and updates the ticket
```

Backlog-level orchestration outside, lifecycle-level orchestration inside.

An implementation child (in any pattern) can also use SDK subagents internally for bounded lookups — a build worker might call a reviewer subagent for help before returning its final status — without the campaign-level controller ever knowing.

---

## Choosing Between Deterministic Code and an LLM Controller

| Controller type | Good when | Examples |
|---|---|---|
| Deterministic code | Decision is mechanical: next pending task, gate on a status string | This repo's `orchestrate_once.py`, `run_supervisor.py` |
| LLM following a skill | State is natural language (issues written by humans) and the decision needs judgment | [LXA](https://github.com/jpshackelford/lxa), [Vibe Manager](https://github.com/rbren/vibe-manager) |

Start deterministic. Add the model where mechanical rules stop being enough.
