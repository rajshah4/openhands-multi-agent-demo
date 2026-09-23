# Implement Approved Spec Automation

This OpenHands prompt-preset automation turns a GitHub label into a bounded,
multiagent implementation workflow:

```text
issues.labeled: openhands-implement-spec
  -> OpenHands automation
  -> repository-local implement-spec skill
  -> Agent Canvas / TaskToolSet implementers
  -> one validated pull request
  -> human review and merge
```

This is event-triggered **Approach 1: bounded in-conversation delegation**. The
GitHub label starts one bounded parent conversation, while `implement-spec`
uses subagents to work the ready frontier of a ticket dependency graph. Because
no later controller must recover and continue the same lifecycle, the trigger
does not make it a durable Approach 3 workflow.

## Register On Rajistics

Preview the exact API request without creating anything:

```bash
python3 scripts/register_implement_spec_automation.py \
  --env-file /path/to/install_replicate/.env \
  --dry-run
```

Register it:

```bash
python3 scripts/register_implement_spec_automation.py \
  --env-file /path/to/install_replicate/.env \
  --apply
```

Defaults target `rajshah4/openhands-multi-agent-demo` on `main`. Override them
with `--repository`, `--repo-url`, and `--ref`.

The registration helper creates the automation through the OpenHands prompt
preset API. The GitHub integration must already be connected. Add the
`openhands-implement-spec` label to an issue only after its committed spec and
tickets are ready.

## Runtime Preflight

The stored `enable_sub_agents` setting is not sufficient evidence that the
runtime exposes native delegation. The prompt requires a live `task`-tool
check and stops instead of silently falling back to single-agent execution.

Local Agent Canvas can run the same repo-local skill directly. A local Canvas
that cannot receive GitHub webhooks can pair it with a polling automation
instead.
