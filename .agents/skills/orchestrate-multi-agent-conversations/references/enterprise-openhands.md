# Enterprise OpenHands Reliability Notes

## Contents

- Conversation API layers
- Conversation and sandbox boundaries
- Agent profiles and ACP
- State and final-response timing
- Secret handoff
- Repository selection
- Automation registration
- Automation and campaign memory
- Failure classification
- Observability
- Validation checklist

## Conversation API Layers

Use first-class Conversation V1 endpoints for parent-child workflows:

```text
POST /api/v1/app-conversations
GET  /api/v1/app-conversations/start-tasks?ids=<start-task-id>
GET  /api/v1/app-conversations?ids=<conversation-id>
GET  /api/v1/conversation/<conversation-id>/events/search
```

Creation is asynchronous. The create response is a start task, not a running conversation. Poll it to `READY`, then use `app_conversation_id` for status and events.

Keep app-server conversations distinct from lower-level runtime conversations. Use the app-server API when children must appear in the OpenHands UI.

## Conversation And Sandbox Boundaries

A first-class conversation preserves independent history, ownership, and an
operator-visible audit trail. It does not always imply a dedicated sandbox.
Enterprise may place trusted conversations in separate sandboxes or group them
in one sandbox according to the installed configuration.

Use isolated sandboxes across tenant, trust, credential, or failure boundaries.
Use bounded grouping only for trusted work. Assign one controller or outer
automation as the grouped sandbox lifecycle owner; do not let one child pause a
sandbox while siblings still use it.

First-class conversation creation does not guarantee isolation. When placement
must be deterministic:

1. check visible sandbox capacity;
2. create a sandbox through `POST /api/v1/sandboxes`;
3. wait for it to reach `RUNNING`;
4. prepare it if needed;
5. send its `sandbox_id` in `POST /api/v1/app-conversations`;
6. persist both IDs before advancing.

This explicit creation and attachment path was live-verified on Enterprise
0.24.0. Explicit attachment can also intentionally place trusted
conversations in one prepared environment; it does not make that shared
sandbox an isolation boundary.

## Correlation Tags

Use short lowercase alphanumeric tags for campaign, task, attempt, and
controller IDs. The tested agent-side `PATCH` replaces the complete tag map, so
read the current record, merge the new tags, patch the complete map, and then
re-read to verify it. Agent-side tags become visible on the app record
asynchronously.

Do not store prompts, credentials, result contracts, or campaign state in
tags. They correlate OpenHands records with the durable application ledger;
they do not replace it.

## Agent Profiles And ACP

Enterprise and Agent Canvas can both resolve saved agent profiles at
conversation creation. Send `agent_profile_id` when a worker should use a
specific native OpenHands or ACP-backed profile. Do not also send a direct
model override: the profile owns its agent and model configuration.

ACP changes the worker implementation, not the orchestration contract.
Continue to assign one bounded responsibility, require a parseable final
response, and validate the result independently.

## State And Final-Response Timing

Enterprise list records and durable events can converge at different times.

Observed failure mode:

1. A child reaches `finished`.
2. Its runtime sandbox later becomes `PAUSED`.
3. The app-conversation list record returns an empty `execution_status`.
4. A parent that trusts only that record waits until its watchdog expires.

Recover terminal status from the durable event stream. Treat `FinishAction`, `ConversationErrorEvent`, and terminal `ConversationStateUpdateEvent` values as evidence.

For the low-latency path, connect to the agent-server WebSocket with
first-message session authentication and `resend_mode=all`. Treat a per-field
`execution_status=finished` event as provisional because a stop hook can resume
execution. Wait for `full_state.execution_status=finished`; `error` and `stuck`
are authoritative immediately. Keep periodic REST reconciliation for lost
sockets, callbacks, and controller restarts.

Terminal status can also precede final-message indexing. After terminal state, poll events for a short bounded grace period. If the final response remains absent, record `needs-human` and provide the child link. Never wait indefinitely and never invent a result from commits or side effects alone.

`GET /server_info` exposes sandbox-wide idle information. Use it for grouped
sandbox lifecycle decisions, never as proof that a particular conversation
succeeded. Persist sanitized app-record usage metrics with the attempt and
identify whether each metric came from the app record, event fallback, or an
infrastructure estimate.

## Pause And Idempotent Cleanup

Pause when a worker may resume within a bounded recovery window. Delete only
after the validated response and required workspace artifacts are durable.
Before deleting a sandbox, confirm no sibling conversation still uses it.

Deleting the last conversation can automatically remove its prepared sandbox.
Treat an already-missing conversation, a `404` on the subsequent sandbox
delete, and a null sandbox tombstone as successful idempotent cleanup. Never
force-delete a shared sandbox based only on idle time.

Verified implementation and evidence:
<https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-workflow-primitives>

## Secret Handoff

Runtime secrets may exist in the sandbox but fail to reach a helper unless the command explicitly references them.

Use create-time Conversation V1 secrets for children. Explicitly bind the variable in the command without echoing it:

```bash
HF_TOKEN="${HF_TOKEN:-}" python3 path/to/helper.py
```

For a parent factory, reference required variables before launch:

```bash
export HF_TOKEN="${HF_TOKEN:-}"
python3 scripts/run_factory.py
```

Avoid post-create secret attachment because it can race child startup. Avoid secret-store fallback and environment-debug dumps in demo paths. Report missing capabilities, not variable names, values, lengths, or full availability matrices.

Once the helper confirms the variable is present, classify later failures as provider, model-output, network, quota, or tool failures rather than missing credentials.

## Repository Selection

Set `selected_repository` and `selected_branch` during child creation. Repeat them in the prompt and require the child to verify its workspace before editing.

Do not ask a child to discover the repository from the issue text. Do not rely on whichever clone happens to exist in a new sandbox. Avoid printing token-bearing remote URLs during verification.

## Automation Registration

Credentials can have API-specific scopes. Test authentication separately against automation registration, conversation creation, and conversation event endpoints. A key that works for conversations may receive `401` from the automation API.

When replacing a live automation:

1. Register the replacement disabled or with mutually exclusive filters when possible.
2. Verify host, event source, repository ref, model profile, timeout, and visible prompt.
3. Enable the replacement.
4. Disable the old automation before creating a validation event.
5. Create one fresh issue or ticket and confirm that exactly one parent starts.

Prefer event-driven triggers. Use exclusion labels or filters to prevent unrelated demo workflows from launching duplicate parents.

## Automation And Campaign Memory

Treat the automation service as the owner of *when* a controller runs. The
trigger may be cron, webhook, or manual dispatch. The controller tick owns
*what happens next*: reconcile existing conversations, validate completed work,
claim bounded new work, checkpoint state, and exit.

Do not rely on the automation conversation or sandbox as campaign memory.
Store task claims, run and attempt IDs, start-task and conversation IDs,
validation results, and checkpoints in application-owned durable state.

Use the built-in automation KV store when one custom automation needs state
across ephemeral runs and `AUTOMATION_KV_TOKEN` is available. Files plus Git
can also connect separate runs when one serialized controller owns the
campaign and reviewable checkpoints matter. Use an application database or
another real lease service when controllers can claim work concurrently.
Registering or successfully triggering an automation is not proof that the
campaign advanced.

## Failure Classification

Keep these states separate:

| Stage | Example result | Parent response |
| --- | --- | --- |
| Preflight | Missing capability | Stop before LLM call |
| Start task | `ERROR` or no conversation ID | `needs-human` |
| Child execution | `error`, `stuck`, timeout | `needs-human` with link |
| State reconciliation | `PAUSED` plus durable `finished` | Continue to final-response grace |
| Contract | Missing or malformed fields | `needs-human` |
| Review gate | `blocking: yes` | Stop before QA |
| Provider | Credential present but provider fails | Provider/tool failure |

Do not let a child exception crash the parent before lifecycle artifacts are written.

## Observability

Track immutable identifiers:

- automation ID and run ID
- sandbox ID
- parent conversation ID
- child conversation IDs
- issue or ticket key
- branch and PR number

Titles are presentation metadata and can be renamed automatically. Automation run records may not expose `conversation_id` until completion. Locate active parents by sandbox ID when necessary.

Log state transitions and periodic heartbeats, but keep logs customer-safe. Do not print complete prompts, complete event payloads, environment dumps, secret inventories, or token-bearing Git remotes.

## Validation Checklist

Before calling a factory reliable, verify:

- deterministic preflight passes without package installation
- an unlabeled test event triggers exactly one parent when labels are not required
- every child starts in the intended repository and branch
- child terminal state is recoverable from durable events
- delayed final-response indexing is bounded
- malformed and missing contracts become `needs-human`
- blocking review findings stop downstream cells
- successful cells advance in order
- Jira or GitHub receives concise links and statuses
- the automation reaches terminal completion before its watchdog
- humans retain PR approval and merge decisions
- production and cloud mutations use dry-run or remain untested and documented
