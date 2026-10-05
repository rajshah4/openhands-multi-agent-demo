# Multi-Agent Orchestration Quickstart

This repository demonstrates practical approaches to coordinate multiple OpenHands agents in production workflows.

## Three Approaches at a Glance

| Approach | Use Case | Start Here |
|----------|----------|-----------|
| **1. In-Conversation Delegation** | One agent needs bounded specialist help within a single run | `shared_workspace.py` |
| **2. Parent-Child Lifecycle** | One request needs an accountable supervisor plus separately visible workers | `patterns/parent-child/run_supervisor.py` |
| **3. Durable Async Workflow** | Workflow must resume after controller restarts | `patterns/polling/orchestrate_once.py` |

## Quick Start

### View a Dry Run

See how the controllers work without creating conversations:

```bash
# Approach 3: Polling reconciliation
cd patterns/polling
python3 orchestrate_once.py --dry-run

# Approach 2: Supervised workers  
cd ../parent-child
python3 run_supervisor.py --dry-run
```

### Run a Full Example

```bash
# Approach 1: In-conversation task delegation
python3 shared_workspace.py
```

## Key Concepts

- **Coordination**: Who observes progress and makes next-step decisions? (parent run, supervisor, reconciler, event handler)
- **Worker Identity**: Are workers long-lived services or ephemeral conversations?
- **State Persistence**: Where does workflow state survive when a controller run ends?
- **Result Flow**: How do results move between agents?

## Documentation

- [Choosing an Approach](./choosing-a-pattern.md) — Decision guide for your workflow
- [Architecture Patterns](./architecture-patterns.md) — Deep dive into each coordination model
- [Best Practices](../BEST_PRACTICES.md) — Reliability patterns for production systems
- [API Reference](./api-reference.md) — Common utilities and interfaces

## Repository Structure

```
.
├── shared_workspace.py          # Approach 1: In-conversation delegation
├── multi_server_isolation.py    # Approach 1: Isolated multi-server example
├── cloud_conversations.py       # Cloud platform setup examples
├── patterns/
│   ├── parent-child/            # Approach 2: Supervised workers
│   ├── polling/                 # Approach 3: Durable workflows
│   └── common/                  # Shared utilities
├── automations/                 # Automation definitions
├── scripts/                     # Setup and registration scripts
├── docs/                        # Additional documentation
├── openwiki/                    # Auto-generated reference docs
└── tests/                       # Test suite
```

## Next Steps

1. Read [Choosing an Approach](./choosing-a-pattern.md) to pick the pattern that fits your workflow
2. Run the relevant dry run to understand the controller logic
3. Adapt the working example to your domain
4. Review [Best Practices](../BEST_PRACTICES.md) for production reliability

For more details, see [README.md](../README.md) and [PATTERNS.md](../PATTERNS.md).
