# Working Examples

Runnable demos in this repo and external reference projects that demonstrate each orchestration pattern at production scale.

## In This Repository

### Shared workspace (SDK subagents + ACP)

**File:** [`shared_workspace.py`](../shared_workspace.py)

Three-vendor pipeline: Claude Code implements, Gemini CLI writes tests, OpenHands reviews. Demonstrates native SDK subagents (`TaskToolSet`) and ACP-backed harnesses in one shared workspace. Supports `--no-claude` to run with OpenHands agents only.

```bash
export LLM_API_KEY="..."
python3 shared_workspace.py
python3 shared_workspace.py --no-claude
```

### Cloud conversations (coding harnesses in managed sandboxes)

**File:** [`cloud_conversations.py`](../cloud_conversations.py)

Each harness gets its own OpenHands Cloud conversation. Communication happens through the git repo. Each conversation's URL is printed as it starts so you can watch it live.

```bash
export OPENHANDS_API_KEY="..."
python3 cloud_conversations.py
python3 cloud_conversations.py --task csv-tool
```

### Isolated local pattern

**File:** [`multi_server_isolation.py`](../multi_server_isolation.py)

Full local isolation via separate git clones. Each agent works in its own clone; results travel through git. Higher operational complexity than the cloud path but no external dependencies.

### Polling reconciliation loop

**Directory:** [`patterns/polling/`](../patterns/polling/)

A restartable reconciliation tick. Run individual ticks by hand to watch the state machine advance. State lives in `state.json`, `WORKLOG.md`, and `results/task-*.md`.

```bash
cd patterns/polling
python3 orchestrate_once.py --dry-run   # preview
python3 orchestrate_once.py             # run a real tick
python3 orchestrate_once.py --watch --interval-seconds 60
```

Supports `--runtime canvas` to spawn workers as visible local conversations.

### Parent-child supervisor

**Directory:** [`patterns/parent-child/`](../patterns/parent-child/)

A live supervisor that starts plan, build, and check conversations in order, gates on each child's final-response contract, and writes a lifecycle report.

```bash
cd patterns/parent-child
python3 run_supervisor.py --dry-run
python3 run_supervisor.py --request "a Python slugify(text) function"
```

Output in `runs/<run-id>/`: per-child prompt and final response, plus `lifecycle-report.md`.

Supports `--runtime canvas` to show children as visible Canvas conversations.

### Event-driven implement-spec automation

**Directory:** [`automations/implement-approved-spec/`](../automations/implement-approved-spec/)

Apply the label `openhands-implement-spec` to a GitHub issue → an implementation automation runs the `implement-spec` skill → agent produces a PR with plan, implementation, and review → human decides whether to merge. Registration script: [`scripts/register_implement_spec_automation.py`](../scripts/register_implement_spec_automation.py).

---

## External Reference Projects

| Project | Approach | What it demonstrates |
|---|---|---|
| [SDLC Automation Demo](https://github.com/rajshah4/sdlc-automation-github-demo) | Approach 3B event handoffs + Approach 2 supervised lifecycle | GitHub-native build → review → QA pipeline; production event-driven implementation |
| [Agent Canvas SDLC Starter](https://github.com/rajshah4/agent-canvas-sdlc-starter) | Approach 2 supervised lifecycle | Visual local supervisor with implementation, review, and QA conversations |
| [OpenHands Agent Research Lab](https://github.com/rajshah4/openhands-agent-research-lab) | All approaches (experiments) | Bounded experiments, deterministic validation, durable attempts, placement evidence, evidence-backed memory |
| [`pr-workflow` plugin](https://github.com/jpshackelford/.openhands/tree/main/plugins/pr-workflow) | Approach 3A reconciliation | Generic cron-driven repository reconciliation using GitHub and a Git-backed worklog; succeeds `ohtv-workflow` |
| [LXA](https://github.com/jpshackelford/lxa) | Approach 3A (long-horizon) | Long-horizon SDK execution plus a GitHub-backed scheduled orchestrator with LLM judgment |
| [Vibe Manager](https://github.com/rbren/vibe-manager) | Approach 3A (conditional LLM) | Deterministic polling that conditionally invokes an LLM manager only when an actionable change needs judgment |

---

## Reusing the Orchestration Skill

The [`orchestrate-multi-agent-conversations`](../.agents/skills/orchestrate-multi-agent-conversations/) skill in `.agents/skills/` guides an agent through execution boundaries, worker selection, control patterns, durable state, result contracts, recovery, capacity, cleanup, and human gates.

Copy the complete skill directory — including `references/` and the validator script — into `.agents/skills/` of another repository and invoke it with `$orchestrate-multi-agent-conversations`.
