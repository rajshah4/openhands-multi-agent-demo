# Quickstart

Get any of the three demo patterns running in a few minutes.

## Prerequisites

- Python 3.10+
- An OpenHands API key (`OPENHANDS_API_KEY`) or a local Agent Canvas instance
- Optional: `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` for the ACP multi-harness demos

## 1. Clone and Install

```bash
git clone https://github.com/rajshah4/openhands-multi-agent-demo
cd openhands-multi-agent-demo
pip install openhands-ai
```

## 2. Try Without Any API Key

Both pattern scripts have a `--dry-run` flag that prints the control decisions and API payloads without starting any conversation.

```bash
# Reconciliation tick — see what one polling loop step decides
cd patterns/polling
python3 orchestrate_once.py --dry-run

# Live supervisor — see the lifecycle plan without calling the API
cd ../parent-child
python3 run_supervisor.py --dry-run
```

## 3. Run the Polling Loop (automations / reconciliation)

```bash
export OPENHANDS_API_KEY="your-key"

cd patterns/polling
python3 orchestrate_once.py         # tick 1: claims task-1, spawns worker, exits
python3 orchestrate_once.py         # tick 2: worker running → quiet tick
python3 orchestrate_once.py         # tick 3: worker done → records result
```

Watch multiple ticks automatically:

```bash
python3 orchestrate_once.py --watch --interval-seconds 60
```

State lives in three files the orchestrator creates:

```
state.json        # backlog statuses and active worker
WORKLOG.md        # append-only log of every tick
results/task-*.md # each worker's final response
```

Reset and run again: `python3 orchestrate_once.py --reset`

## 4. Run the Parent-Child Supervisor

```bash
export OPENHANDS_API_KEY="your-key"
cd patterns/parent-child

python3 run_supervisor.py --request "a Python function slugify(text) that converts titles into URL-safe slugs"
```

When the run finishes, `runs/<run-id>/` contains a prompt and final response for each child conversation plus a `lifecycle-report.md` for human review.

## 5. SDK Subagents in a Shared Workspace

```bash
export LLM_API_KEY="your-key"
export ANTHROPIC_API_KEY="..."  # optional — for Claude Code harness
export GEMINI_API_KEY="..."     # optional — for Gemini CLI harness
python3 shared_workspace.py
```

Pass `--no-claude` to skip the ACP harnesses and use only OpenHands agents.

## 6. Run on Local Agent Canvas

Both pattern scripts accept `--runtime canvas`. Workers become separate visible conversations in the Canvas UI:

```bash
python3 patterns/polling/orchestrate_once.py --runtime canvas
python3 patterns/parent-child/run_supervisor.py --runtime canvas
```

Canvas reads its API key from `AGENT_CANVAS_API_KEY` (env var) or `~/.openhands/agent-canvas/session-api-key.txt` (auto-saved when local Canvas starts), falling back to `api-key.txt` in the same directory.

## 7. Run the Tests

```bash
pip install pytest
pytest tests/ -v
```

The tests are offline and check the controller logic without calling the API.

## Self-hosted or Enterprise

Point all scripts at your instance before running:

```bash
export OPENHANDS_BASE_URL="https://openhands.your-company.com"
```

## Next Steps

- [Core Concepts](concepts.md) — understand the three decisions before adapting the demos
- [Orchestration Patterns](patterns.md) — when to use each pattern
- [Working Examples](examples.md) — external reference projects
