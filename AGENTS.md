# Multi-Agent Orchestration Demo — Repository Knowledge

## Overview

This repository demonstrates three practical approaches to coordinate multiple OpenHands agents in production workflows:

1. **In-Conversation Delegation** — One parent conversation with ephemeral helpers
2. **Parent-Child Lifecycle** — Supervisor with supervised workers
3. **Durable Async Workflow** — Polling or event-driven controller with durable state

## Build & Run

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/
```

### View Controller Logic (Dry Run)
```bash
# Approach 1: In-conversation delegation
python3 shared_workspace.py --help

# Approach 2: Parent-child lifecycle
cd patterns/parent-child
python3 run_supervisor.py --dry-run

# Approach 3: Durable polling controller
cd ../polling
python3 orchestrate_once.py --dry-run
```

### Run Full Examples

```bash
# Approach 1 (requires OpenHands environment)
python3 shared_workspace.py

# Approach 2
cd patterns/parent-child
python3 run_supervisor.py --agent-server-url http://localhost:8001

# Approach 3
cd patterns/polling
python3 orchestrate_once.py --agent-server-url http://localhost:8001
```

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `shared_workspace.py` | Approach 1: In-conversation delegation with ephemeral helpers |
| `multi_server_isolation.py` | Approach 1: Variant with isolated multi-server setup |
| `cloud_conversations.py` | Cloud platform configuration examples |
| `patterns/parent-child/` | Approach 2: Supervisor with supervised workers |
| `patterns/polling/` | Approach 3: Durable polling controller |
| `patterns/common/` | Shared conversation utilities |
| `automations/` | Automation definitions for production deployment |
| `scripts/` | Setup and registration scripts |
| `docs/` | Additional design documentation |
| `openwiki/` | Auto-generated reference documentation |

## Documentation

**Start here:**
- [Quickstart](openwiki/quickstart.md) — Get started in 5 minutes
- [Choosing an Approach](openwiki/choosing-a-pattern.md) — Decision guide

**Learn more:**
- [Architecture Patterns](openwiki/architecture-patterns.md) — Deep dive into each pattern
- [API Reference](openwiki/api-reference.md) — Common interfaces and utilities
- [BEST_PRACTICES.md](BEST_PRACTICES.md) — Production reliability patterns
- [PATTERNS.md](PATTERNS.md) — Detailed design patterns

## Code Style

- Python 3.10+
- Follow PEP 8 conventions
- Type hints required for public functions
- Docstrings for classes and public methods

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_patterns.py::test_approach_one

# Run with coverage
pytest --cov tests/
```

## Common Tasks

| Task | Command |
|------|---------|
| Start a pattern example | `cd patterns/[pattern] && python3 *.py --help` |
| View pattern dry run | `python3 [script].py --dry-run` |
| Debug a controller | `python3 [script].py --verbose --max-iterations 1` |
| Check pattern validity | `pytest tests/test_guidance.py` |

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENHANDS_API_KEY` | API key for OpenHands Cloud | `oh_sk_...` |
| `AGENT_SERVER_URL` | Local Agent Canvas URL | `http://localhost:8001` |
| `REPO_URL` | Git repository to clone | `https://github.com/owner/repo` |
| `REPO_BRANCH` | Git branch | `main` |

## Patterns Overview

### Approach 1: In-Conversation Delegation
**File:** `shared_workspace.py`  
**Use when:** One agent needs bounded, temporary help from specialists  
**Tradeoff:** Sequential, no durability across restarts

### Approach 2: Parent-Child Lifecycle
**File:** `patterns/parent-child/run_supervisor.py`  
**Use when:** Request needs supervisor plus separately visible workers  
**Tradeoff:** Workers don't persist across requests

### Approach 3: Durable Async Workflow
**File:** `patterns/polling/orchestrate_once.py`  
**Use when:** Workflow must resume after controller restarts  
**Tradeoff:** Higher complexity, persistent state required

## Contributing

1. Pick an approach to extend
2. Read [BEST_PRACTICES.md](BEST_PRACTICES.md) for reliability patterns
3. Add tests to `tests/`
4. Follow code style above

## Additional Resources

- [OpenHands SDK Docs](https://docs.openhands.dev/sdk)
- [Agent Canvas Guide](docs/agent-canvas-and-acp.md)
- [Orchestration Taxonomy](docs/choosing-a-pattern.md)

---

**Autodocs Reference:**
This repository uses automated documentation generation. See [openwiki/](openwiki/) for generated reference docs.
Last updated: 2026-10-05 by autodocs.
