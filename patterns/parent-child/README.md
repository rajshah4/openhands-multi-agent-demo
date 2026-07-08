# Pattern 1: Parent-Child

A live parent orchestrator runs a complete lifecycle of child conversations,
**now**. The parent waits for each child; contrast with the
[polling loop](../polling/), which never waits.

```text
request
  -> parent (this script, or a parent conversation)
    -> child: plan
    -> child: build
    -> child: check
  -> lifecycle report
```

Use this pattern when one request should produce one complete, visible
lifecycle: the supervisor stays alive for the run, starts each child in order,
gates on each child's final response, and writes a report a human can act on.

## Run It

```bash
export OPENHANDS_API_KEY="your-key"
# Self-hosted or Enterprise? Point at your instance:
# export OPENHANDS_BASE_URL="https://openhands.your-company.com"

python3 run_supervisor.py --request "a Python function slugify(text) that converts titles into URL-safe slugs"
```

You will see each child conversation's URL as it starts (open it to watch),
and when the run finishes:

```text
runs/<run-id>/
  plan.prompt.md      # exactly what each child was told
  plan.final.md       # exactly what each child reported back
  build.prompt.md
  build.final.md
  check.prompt.md
  check.final.md
  children.json
  lifecycle-report.md # the summary a human reviews
```

No API key yet? See the mechanics without calling anything:

```bash
python3 run_supervisor.py --dry-run
```

Running local Agent Canvas? Children become visible local conversations:

```bash
python3 run_supervisor.py --runtime canvas
```

Canvas uses a different API than Cloud/Enterprise (and a shared working tree
instead of isolated sandboxes) - see
[Agent Canvas and ACP](../../docs/agent-canvas-and-acp.md).

## The Three Ideas That Make It Work

**1. The contract is the interface.** Each child ends its final response with a
small parseable block:

```text
status: done | pass | findings | needs-human | failed
summary: <one line>
next_gate: <next-cell-or-stop>
```

The supervisor gates on `status` alone - it never reads a child's event log.
If a child returns `needs-human` or `failed`, the lifecycle stops and says so.

**2. Children are sandboxed, so evidence travels in the final response.** Each
child runs in its own sandbox. Files it writes are invisible to the supervisor
and to later cells. That is why every prompt says: paste the implementation,
the tests, and the real test output into your final response. (When children
work on a real repository, durable output travels through git - a branch or a
PR - instead. See the state-model notes in the
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo).)

**3. Each cell distrusts the previous one just enough.** The check cell
re-runs the build cell's tests itself and probes edge cases the build skipped.
That is the difference between a pipeline and a lifecycle with gates.

## The Same Pattern, Grown Up

This demo keeps the work trivial so the pattern is the star. The identical
shape - parent conversation, bounded children, final-response contracts, human
gates - runs a real software factory in
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo):

| Here (teaching) | There (software factory) |
| --- | --- |
| `plan` -> `build` -> `check` | `story-to-pr` -> `code-review` -> `qa` |
| Request is a one-liner | Request is a Jira ticket or GitHub issue |
| Evidence in final responses | Evidence in branches, PRs, Playwright artifacts |
| Script is the supervisor | A parent OpenHands conversation is the supervisor |
| Report on disk | Report + PR sections + Jira comment |

That repo has two live-validated variants: OpenHands Enterprise/Cloud
(Jira-triggered) and Agent Canvas (local, visible conversation graph).

## Adapt It

| Replace | With |
| --- | --- |
| The cells | Any bounded stages: research -> draft -> critique, migrate -> verify, triage -> fix -> test |
| The workers | OpenHands conversations (default), or ACP-connected harnesses like Claude Code / Gemini CLI - see [Agent Canvas and ACP](../../docs/agent-canvas-and-acp.md) |
| The trigger | Run the script by hand, from a webhook, from a Jira/GitHub automation, or start the supervisor as an OpenHands conversation itself |
| The gates | Whatever statuses your workflow needs - keep the vocabulary small |

Keep the rule stable: the supervisor orchestrates and gates; children own
bounded work; humans keep authority over anything irreversible.
