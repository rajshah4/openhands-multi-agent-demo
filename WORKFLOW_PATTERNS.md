# Workflow Patterns

This repo now separates two decisions:

1. **Runtime pattern:** where agents run and how isolated they are.
2. **Workflow pattern:** how work advances from one agent to the next.

`PATTERNS.md` covers the runtime axis. This guide covers the workflow axis.

## Pattern Catalog

| Workflow pattern | Example | Best for | Control model |
| --- | --- | --- | --- |
| **Linear multi-agent pipeline** | `shared_workspace.py`, `multi_server_isolation.py`, `cloud_conversations.py` | A bounded implement -> test -> review demo | The script waits for each phase before starting the next. |
| **Parent-child supervisor** | `parent_child_supervisor.py` | One request should produce a complete lifecycle report | One parent stays alive, starts child conversations, gates on final responses, and writes a summary. |
| **Polling continuation loop** | `polling_continuation_loop.py` | Workflows that may span hours or days | A cron wakes the orchestrator every 15 minutes, checks state, takes at most one action, logs, and exits. |

These patterns can run on any runtime pattern. For example, a parent-child
supervisor can use Enterprise-managed sandboxes, local isolated clones, or a
single shared SDK workspace.

## Linear Multi-Agent Pipeline

Use this when the workflow has a known sequence and a short expected duration.

```text
request
  -> implementer
  -> tester
  -> reviewer
  -> final summary
```

The orchestrator is synchronous: it starts an agent, waits for completion,
passes state forward, and starts the next agent.

Representative files:

- `shared_workspace.py`: shared local workspace, low setup.
- `multi_server_isolation.py`: local isolated clones, explicit git handoff.
- `cloud_conversations.py`: Enterprise/Cloud conversations, one sandbox per
  phase.

Use this pattern when:

- the work is bounded enough to finish in one run
- phase order is known up front
- failures can stop the script immediately
- a human wants to watch a simple implement/test/review story

## Parent-Child Supervisor

Use this when one request should start a complete workflow but the work still
needs visible child conversations and human gates.

```text
event or prompt
  -> parent supervisor conversation
    -> child: story-to-pr
    -> child: code-review
    -> child: QA
  -> lifecycle report
```

The parent stays alive for the run. It owns orchestration, not domain work. Each
child receives a self-contained prompt and returns a small final response
contract:

```text
status: done | findings | needs-human | failed
artifact: factory_runs/<run-id>/<cell>.final.md
summary: <short result>
next_gate: <next-cell-or-stop>
```

The parent gates on that contract and writes the lifecycle report.

Run the local teaching example:

```bash
python parent_child_supervisor.py
python parent_child_supervisor.py --status code-review=needs-human
```

Use this pattern when:

- a single ticket or request should run the whole workflow
- every child conversation should remain inspectable
- the parent needs to report back to Jira, GitHub, Linear, or another system of
  record
- humans still own scope, merge, deployment, production access, and security
  exceptions

## Polling Continuation Loop

Use this when the workflow should keep moving over time without one long-lived
orchestrator waiting for every worker.

```text
cron every 15 minutes
  -> wake
  -> check durable state
  -> decide one action
  -> maybe spawn one worker
  -> append worklog marker
  -> exit
```

This pattern is inspired by the OHTV workflow plugin. That plugin wakes on a
cron schedule, checks GitHub issues/PRs and active conversations, spawns focused
workers, writes machine-readable worklog markers, and exits. The next wake-up
continues from state.

Run the local teaching example:

```bash
python polling_continuation_loop.py --dry-run
python polling_continuation_loop.py
python polling_continuation_loop.py --clear-active-workers
```

The key invariant is **one action per wake-up**. The orchestrator does not try
to finish the whole lifecycle. It advances the system one durable step, then
lets the next scheduled run re-evaluate.

Use this pattern when:

- the workflow may take hours or days
- workers can run in parallel slots
- state lives in GitHub, Jira, Linear, a worklog, or a small durable state file
- you want automatic continuation without a forever-running parent
- the automation should auto-disable after repeated quiet periods

## Choosing A Workflow Pattern

| Need | Choose |
| --- | --- |
| Short demo, known sequence, easy to explain | Linear pipeline |
| One request kicks off a full visible lifecycle | Parent-child supervisor |
| Long-running backlog/PR flow that should keep nudging itself forward | Polling continuation loop |
| Human review before every step | Do not fully automate; use label or webhook gates |

## Polling Pattern Checklist

- Keep state durable: issue labels, PR comments, worklog markers, or a KV store.
- Limit each wake-up to one action.
- Track active worker conversations before spawning more.
- Use stable markers such as `<!-- orchestrator-status: spawn -->`.
- Count quiet wake-ups and disable the automation after a threshold.
- Make every worker bounded: it should finish and report, not become the
  orchestrator.
- Prefer a 15-minute cron for active projects; slow it down when work is quiet.

## Sources And Inspirations

- OHTV workflow plugin:
  https://github.com/jpshackelford/.openhands/tree/main/plugins/ohtv-workflow
- SDLC parent-child delegated factory pattern:
  https://github.com/rajshah4/sdlc-automation-github-demo
