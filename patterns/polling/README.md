# Pattern 2: Polling Loop

A stateless orchestrator wakes on a schedule, takes at most one action, and
exits. The work outlives the orchestrator - **durable state is the memory**.

```text
wake -> read state -> decide -> (spawn | record | quiet) -> log -> exit
  ^                                                                 |
  '------------------------- next tick ----------------------------'
```

Use this pattern when the work is an ongoing backlog rather than one request:
work that spans hours or days, waits on slow externals (CI, human review), and
must survive any individual run crashing. The orchestrator never waits for a
worker - it checks back on the next tick. (If you know Kubernetes, this is a
controller or reconciliation loop: observe actual state, compare to desired
state, take one convergent action, exit.)

## Run It

Each run of `orchestrate_once.py` is one tick. Run ticks by hand and watch the
state machine advance:

```bash
export OPENHANDS_API_KEY="your-key"
# Self-hosted or Enterprise? Point at your instance:
# export OPENHANDS_BASE_URL="https://openhands.your-company.com"

python3 orchestrate_once.py   # tick 1: claims task-1, spawns a real worker, exits
python3 orchestrate_once.py   # tick 2: worker still running -> quiet tick
python3 orchestrate_once.py   # tick 3: worker finished -> records result to results/task-1.md
python3 orchestrate_once.py   # tick 4: claims task-2 ...
```

Too slow by hand? Loop locally:

```bash
python3 orchestrate_once.py --watch --interval-seconds 60
```

What accumulates on disk (the orchestrator's entire memory):

```text
state.json        # backlog statuses, in-flight worker, quiet-tick counter
WORKLOG.md        # append-only human-readable log of every tick
results/task-*.md # each worker's final response
```

Reset and run it again: `python3 orchestrate_once.py --reset`.
No API key yet? `python3 orchestrate_once.py --dry-run` prints the decision and
the exact API payload without mutating anything. Running local Agent Canvas?
`--runtime canvas` spawns the workers as visible local conversations
in one shared demo folder.

Use a saved native OpenHands or ACP-backed profile on either runtime:

```bash
python3 orchestrate_once.py --runtime canvas --agent-profile-id <profile-id>
```

## The Four Ideas That Make It Work

**1. The orchestrator is stateless; the state is durable.** A tick reads
`state.json`, acts, writes an atomic checkpoint, and exits. A later tick can
resume from the last completed checkpoint. This teaching implementation
assumes one controller; production controllers must also reconcile a crash
during dispatch so they do not create a duplicate worker.

**2. Fire and forget.** A tick that spawns a worker does not wait for it.
Observing the worker is the *next* tick's job. This is what lets the pattern
span work that takes hours (CI runs, human reviews) without holding anything
open.

**3. One action per tick.** Claim one task, or record one result, or stay
quiet. Small convergent steps make every tick cheap, predictable, and easy to
read in the worklog.

**4. Humans pause the loop with a file.** Write anything into
`INSTRUCTIONS.md` and the next tick reports `needs-human` and does nothing
until the file is cleared. The loop is autonomous, not unaccountable. After
two quiet ticks with an empty backlog, the tick reports that a scheduled
automation would disable itself - the loop knows when to stop existing.

## Productionize It

The by-hand ticks and `--watch` are for learning. In production, the tick runs
on a schedule. Two options:

**Cron on any machine that has the repo:**

```cron
*/15 * * * * cd /path/to/repo/patterns/polling && python3 orchestrate_once.py >> cron.log 2>&1
```

**An OpenHands scheduled automation** (cron trigger, no machine of your own):
register a prompt-preset automation whose prompt tells the conversation to run
`orchestrate_once.py` from the cloned repo. See
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo)
for a worked registration script (`scripts/register_replicated_factory_automation.py`)
you can adapt - swap the trigger to `{"type": "cron", "schedule": "*/15 * * * *"}`.

## The Production Reference

This pattern is not hypothetical. The
[ohtv-workflow plugin](https://github.com/jpshackelford/.openhands/tree/main/plugins/ohtv-workflow)
runs its own project's issue-to-merge lifecycle this way: a cron automation
wakes every 30 minutes, reads GitHub issues/PRs/labels as the durable state,
dispatches expansion / implementation / test / review / merge workers into
parallel slots, appends a worklog, and auto-disables after quiet periods.

Two deliberate differences here:

| This demo | ohtv-workflow |
| --- | --- |
| State in `state.json` + `WORKLOG.md` (zero setup) | State in GitHub issues, PRs, and labels (the system of record) |
| Decision loop is deterministic Python | Decision loop is an LLM following an `/orchestrate` skill |

Both are valid points on the same spectrum. Use deterministic code when the
decision is mechanical (cheap, reproducible). Use an LLM orchestrator when the
state is natural language - issues written by humans - and the decision needs
judgment. Migrating this demo toward ohtv means swapping `load_state` for
GitHub queries and (optionally) the decision function for a prompt.

## Adapt It

| Replace | With |
| --- | --- |
| `backlog.json` | GitHub issues/labels, Jira tickets, a queue, a database table |
| The worker prompt | Any bounded job; workers can use native OpenHands or ACP-backed agent profiles |
| One worker slot | Parallel slots for non-conflicting work (ohtv runs issue-work and PR-work slots side by side) |
| The worker itself | An entire bounded parent-child lifecycle |
