---
name: orchestrate-multi-agent-conversations
description: Design, implement, debug, and validate reliable OpenHands multi-agent systems. Use when choosing between isolated or grouped Enterprise conversations, Agent Canvas, and TaskTool subagents; selecting native OpenHands, coding-agent CLI, or ACP-backed workers; choosing a live parent, polling controller, scheduled automation, or event-triggered control loop; selecting files, Git, tickets, or a database for durable state; or implementing Conversation V1 startup, validation, recovery, capacity control, cleanup, and human gates.
---

# Orchestrate Multi-Agent Conversations

Design the execution boundary, control loop, and durable state separately.
Build bounded, observable workflows whose correctness does not depend on an
agent remembering campaign state.

## Follow The Workflow

1. Read repository instructions and current OpenHands guidance before choosing
   an architecture. Establish the deployed OpenHands version and supported
   capabilities.
2. Describe the workload:
   - bounded request or continuing backlog;
   - expected task count, duration, and concurrency;
   - trust and credential boundaries;
   - required conversation history and human handoff;
   - failure, retry, validation, and audit requirements.
3. Read `references/architecture-patterns.md`. Choose one execution boundary,
   one worker implementation, one control pattern, and one durable-state
   boundary. Do not treat them as one decision.
4. State the recommendation before implementing:

```text
execution:
worker:
control:
durable state:
active-work limit:
validation:
cleanup owner:
scale-out boundary:
untested assumptions:
```

5. Implement one common controller contract:

```text
reconcile durable state
  -> check capacity
  -> claim bounded work
  -> start or reattach to conversations
  -> observe durable terminal state
  -> validate independently
  -> record evidence
  -> release execution capacity
```

6. Define one responsibility and one machine-readable output contract per
   worker. Keep task assignment, admission, validation, state transitions, and
   irreversible approvals outside worker self-reports.
7. Run deterministic preflight checks before making LLM calls. Verify the host,
   repository, branch, required capability, state store, capacity limit, and API
   access without printing secrets or detailed secret inventories.
8. Qualify the design in stages: offline state tests, one live worker, bounded
   concurrency, restart recovery, failure injection, cleanup, and then an
   endurance run. Report what each stage establishes and does not establish.
9. Publish a concise lifecycle summary with immutable IDs, worker links,
   validation results, retries, capacity evidence, cleanup state, and the next
   human decision.

## Preserve These Boundaries

- Treat a conversation as an ownership, history, and audit boundary. Treat a
  sandbox as a compute, filesystem, credential, and failure boundary. They are
  not the same thing.
- Do not infer sandbox isolation from first-class conversation creation.
  Enterprise placement follows the installed grouping configuration unless the
  controller explicitly prepares a sandbox and attaches the conversation.
- Treat the worker harness as another independent choice. Native OpenHands,
  a coding-agent CLI, and an ACP-backed profile can fill the same worker role.
  Both Enterprise and Agent Canvas support ACP-backed profiles.
- Treat an automation as a trigger. A continuing campaign also requires a
  controller tick and durable state that later automation runs can reload.
- Use parent/subagent delegation for a bounded work cell. Do not place a
  hundred-task campaign under one parent conversation.
- Use the OpenHands automation KV store or files and Git for one serialized
  controller when restartability is sufficient. Use Git when reviewable
  checkpoints matter. Use an application-owned transactional store when
  controllers or tenants can claim work concurrently.
- Never use OpenHands internal database tables as the application coordination
  API.
- Never infer success from automation, conversation, sandbox, commit, or
  streaming status alone. Parse the worker contract and validate the result
  independently.
- Assign one cleanup owner for every sandbox or grouped work cell. Queue work
  above tested capacity.
- Keep merges, deployments, approvals, and other irreversible actions behind
  explicit human gates.

## Operate Enterprise Conversations Reliably

Create first-class children through `POST /api/v1/app-conversations`. Set the
repository, branch, prompt, model profile, and required secrets at creation.
Use `agent_profile_id` when the child should run a saved native OpenHands or
ACP-backed agent profile.
Poll the asynchronous start task to `READY`, persist its ID and the resulting
conversation ID, then monitor the app-conversation and durable event stream
with bounded timeouts.

When exact placement matters, check capacity, create a sandbox through
`POST /api/v1/sandboxes`, wait for `RUNNING`, and pass its `sandbox_id` at
conversation creation. Apply short correlation tags with read-modify-write
semantics; keep campaign state in the durable application ledger.

Use the agent-server WebSocket for low-latency observation and REST for
reconciliation. A per-field `finished` WebSocket event is provisional; wait
for `full_state.execution_status=finished`. Inspect `/server_info` only for
sandbox-wide idle state, and persist sanitized usage metrics from the app
conversation.

Treat list records as snapshots rather than the only authority. Recover
terminal status from durable events when list state is incomplete. After
terminal state, allow a bounded final-response indexing grace period. Convert
missing or malformed output to `needs-human`.

Pass secrets at child creation and reference required environment variables
without printing them. Do not attach secrets after startup or emit environment
dumps.

Pause resources for a bounded recovery window or delete them after durable
artifacts are preserved. Treat an already-missing conversation, an
automatically deleted final sandbox, and a null sandbox tombstone as successful
idempotent cleanup. Never delete a shared sandbox from idle time alone.

## Bound Controllers

Give each start, execution, final-response, checkpoint, and cleanup phase a
timeout and explicit fallback. Keep controller headroom for reconciliation and
final reporting.

Track automation, controller run, attempt, start-task, conversation, sandbox,
task, branch, ticket, and pull-request identifiers where applicable. Do not
depend on mutable titles.

Emit periodic state names and stable IDs only. Preserve failures and retries as
evidence instead of hiding them behind a final success count.

## Load Supporting Material

- Read `references/architecture-patterns.md` before recommending or changing a
  multi-agent architecture.
- Read `references/enterprise-openhands.md` for Conversation V1 state,
  grouping, automation, secret, observability, and recovery details.
- Read `references/prompt-contracts.md` when writing parent, worker, subagent,
  or gate contracts.
- Use `scripts/validate_child_contract.py` for the bundled contract shapes.
