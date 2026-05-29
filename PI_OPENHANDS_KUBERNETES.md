# Pi Under OpenHands With Kubernetes

This note describes what is possible if a team wants to keep the Pi coding
agent harness while using OpenHands to coordinate multiple isolated workers.

## Short Answer

Yes. OpenHands can act as the control plane while Pi remains the coding
harness inside each worker.

The simplest integration path is ACP:

```text
OpenHands orchestrator
  -> ACPAgent
    -> pi-acp
      -> pi --mode rpc
        -> Pi coding agent
```

That keeps Pi's agent loop, prompts, skills, provider configuration, sessions,
and file/bash tools. OpenHands owns orchestration, task sequencing,
observability, isolation policy, and handoff between workers.

## What The Pi User Keeps

- Pi's own provider/model choices.
- Pi's built-in tools: `read`, `write`, `edit`, `bash`, plus optional read-only
  tools such as `grep`, `find`, and `ls`.
- Pi skills, prompt templates, themes, extensions, packages, and `AGENTS.md`
  context loading.
- Pi sessions via `PI_CODING_AGENT_SESSION_DIR` or `--session-dir`.
- Pi CLI behavior for direct use outside OpenHands.

The one thing they may not keep inside OpenHands is the exact native Pi TUI.
OpenHands sees Pi through ACP messages and tool-call events. If a user wants
the full Pi terminal UI, they can still attach to the worker container or run
Pi directly against the same repo/session volume.

## Runtime Shapes

### 1. Local Smoke Test

Run Pi directly first:

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
pi --version
pi --help
```

Then test the ACP bridge:

```bash
npm install -g pi-acp
pi-acp
```

`pi-acp` speaks ACP JSON-RPC 2.0 over stdio and starts Pi in RPC mode. That
means OpenHands and `pi-acp` should run in the same process namespace unless a
separate network wrapper is added.

### 2. OpenHands Local Worker

Use Pi as another ACP-backed harness, similar to Gemini CLI in
`shared_workspace.py`:

```python
def setup_pi_agent() -> ACPAgent | None:
    return ACPAgent(
        acp_command=["npx", "-y", "pi-acp"],
        acp_env={
            "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
            "PI_ACP_ENABLE_EMBEDDED_CONTEXT": "true",
            "PI_OFFLINE": "1",
        },
    )
```

Use this mode when one OpenHands process is coordinating one or more local
agent subprocesses.

### 3. Kubernetes Workers

For scale-out, run each Pi-backed agent in its own pod or Job:

```text
API / scheduler
  -> OpenHands controller
    -> K8s Job: pi-implementer
    -> K8s Job: pi-tester
    -> K8s Job: pi-reviewer
```

Each worker image should include:

```text
python + OpenHands SDK
node 22+ or newer
@earendil-works/pi-coding-agent
pi-acp
git
test/build tools for the target repo
```

Each worker should receive:

```text
repo checkout or mounted workspace
Pi config/session volume
provider API keys from Kubernetes Secrets
task prompt from OpenHands
git branch, artifact path, or PVC handoff target
resource limits and timeout policy
```

Recommended handoff options:

- Git branch per worker for reviewable, auditable state transfer.
- PVC per task if agents need fast shared filesystem handoff.
- Object storage artifacts for logs, patches, coverage, and test output.

For most teams, git branch handoff is the easiest to reason about because it
matches the existing `multi_server_isolation.py` pattern.

## Container Contract

A minimal worker image would look like this conceptually:

```dockerfile
FROM node:22-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent pi-acp

WORKDIR /workspace
```

In production, pin package versions instead of installing latest:

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.77.0 pi-acp@<tested-version>
```

## Control Plane Responsibilities

OpenHands should own:

- Creating one task per agent phase.
- Starting each local process, container, or Kubernetes Job.
- Passing task prompts and environment.
- Capturing logs and final responses.
- Enforcing timeout, retry, and max-cost policy.
- Coordinating state handoff through git, PVCs, or artifacts.
- Running final review or quality gates.

Pi should own:

- Local coding behavior inside the workspace.
- Model/provider selection.
- Prompt extensions and skills.
- File edits and shell commands.
- Session state and compaction.

## Known Constraints

- `pi-acp` is a stdio adapter, so keep `OpenHands -> pi-acp -> pi` in the same
  container/pod unless a network bridge is added.
- `pi-acp` currently does not make Pi a full OpenHands runtime. It translates
  between ACP and Pi RPC.
- Pi's native TUI is not the same as watching a managed OpenHands conversation.
- A full end-to-end smoke test needs a provider key such as `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`.
- For Kubernetes, secrets, egress policy, workspace cleanup, and per-job cost
  limits need to be designed explicitly.

## Smoke Test Notes

Checked on 2026-05-28:

- `node -v` -> `v25.6.1`
- `npm -v` -> `11.9.0`
- `npm exec --yes --package=@earendil-works/pi-coding-agent -- pi --version`
  -> `0.77.0`
- `pi --help` confirms `--mode rpc`, `--print`, `--session-dir`, provider
  flags, tool allow/deny flags, and the expected provider API key environment
  variables.
- `pi-acp --help` exits successfully but prints no help output in this
  environment.
- A live agent task was not run because no provider API key was supplied for
  this smoke test.

## Useful References

- Pi docs: https://pi.dev/docs/latest
- Pi package move to Earendil Works: https://pi.dev/news/2026/5/7/pi-has-a-new-home
- Pi source repository: https://github.com/earendil-works/pi
- Pi ACP adapter: https://github.com/svkozak/pi-acp
- Zed ACP listing for Pi: https://zed.dev/acp/agent/pi
