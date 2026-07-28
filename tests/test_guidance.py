"""Offline checks for the quick-start documentation and repo-local skill."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "orchestrate-multi-agent-conversations"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def local_markdown_targets(path: Path) -> list[Path]:
    targets: list[Path] = []
    for raw_target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        target = raw_target.split("#", 1)[0]
        if not target or "://" in target or target.startswith("#"):
            continue
        targets.append((path.parent / target).resolve())
    return targets


def test_guidance_local_links_exist() -> None:
    guides = [ROOT / "GETTING_STARTED.md", ROOT / "BEST_PRACTICES.md"]
    missing = [
        target
        for guide in guides
        for target in local_markdown_targets(guide)
        if not target.exists()
    ]
    assert not missing


def test_getting_started_has_quick_start_and_deeper_guidance() -> None:
    text = (ROOT / "GETTING_STARTED.md").read_text(encoding="utf-8")
    assert text.index("## Three Starting Points") < text.index(
        "## Three Parts of Multi-Agent Orchestration"
    )
    assert "## When Each Starting Point Fits" in text
    assert "Software SDK orchestration" in text
    assert "Polling and automations" in text
    assert "Parent-child conversations" in text
    assert "An event triggers the next automation directly" in text
    assert "control starting points, not fixed execution or storage bundles" in text
    assert "### Agent execution: choose the boundary" in text
    assert "### Coordination: choose who advances the work" in text
    assert "### Workflow state: choose what survives" in text
    assert "### Compose the three choices" in text
    assert "Application controller or live parent" in text
    assert "Direct event handoffs" in text
    assert "Application database" in text
    assert text.count("**Code examples:**") >= 3
    assert "patterns/common/openhands_conversations.py" in text
    assert "patterns/common/canvas_conversations.py" in text
    assert "patterns/parent-child/run_supervisor.py" in text
    assert "patterns/polling/orchestrate_once.py" in text
    assert "sdlc-automation-github-demo/tree/main/automations/github" in text
    assert "openhands-agent-research-lab/tree/main/experiments/in-platform-controller" in text
    assert "does not yet include a working multi-controller database" in text
    assert "## Example Compositions" in text
    assert "example combinations, not required pairings" in text
    assert "#### Example: Jira story to reviewed and tested PR" in text
    assert "implementation agent opens a GitHub pull request" in text
    assert "code-review agent posts an independent review" in text
    assert "QA agent runs acceptance checks" in text
    assert "human reviews and decides whether to merge" in text
    assert "#### Example: explicitly isolated build, review, and QA" in text
    assert "writable checkout and branch-push credentials" in text
    assert "clean checkout and read-only PR access" in text
    assert "fresh test environment and test-only credentials" in text
    assert "does not prepare or attach a sandbox" in text
    assert "enterprise-workflow-primitives" in text
    assert "## Alternative Coding Agents and Harnesses" in text
    assert "### Two ways to invoke an alternative coding agent" in text
    assert "### Enterprise or Agent Canvas?" in text
    assert "Command line" in text
    assert "ACP is not specific to Agent Canvas" in text
    assert "not a complete" in text
    assert "Enterprise-versus-Agent-Canvas matrix" in text
    assert "--agent-profile-id" in text
    assert "## Best Practices" in text
    assert "## Repository Map" in text


def test_getting_started_visuals_exist() -> None:
    text = (ROOT / "GETTING_STARTED.md").read_text(encoding="utf-8")
    visuals = [
        ROOT / "assets" / "start-sdk-subagents.svg",
        ROOT / "assets" / "start-automation-controller.svg",
        ROOT / "assets" / "start-enterprise-conversations.svg",
        ROOT / "assets" / "multi-harness-coding-team.svg",
    ]
    assert all(path.exists() for path in visuals)
    assert all(path.name in text for path in visuals)


def test_best_practices_has_neurogolf_operating_lessons() -> None:
    text = (ROOT / "BEST_PRACTICES.md").read_text(encoding="utf-8")
    assert "## Give Every Unit Stable Identity" in text
    assert "## Use An Append-Only Attempt Ledger" in text
    assert "## Make Dispatch Idempotent" in text
    assert "## Limit Active Work And Queue The Rest" in text
    assert "## Assign One Cleanup Owner" in text
    assert "4,800 unique attempt IDs" in text


def test_architecture_keeps_three_decisions_separate() -> None:
    text = (ROOT / "BEST_PRACTICES.md").read_text(encoding="utf-8")
    assert "Choose An Execution Boundary" in text
    assert "Choose A Control Pattern" in text
    assert "Choose Where Workflow State Lives" in text
    assert "OpenHands automation KV" in text


def test_repo_skill_has_required_files() -> None:
    assert (SKILL / "SKILL.md").exists()
    assert (SKILL / "agents" / "openai.yaml").exists()
    assert (SKILL / "references" / "architecture-patterns.md").exists()
    assert (SKILL / "references" / "enterprise-openhands.md").exists()
    assert (SKILL / "references" / "prompt-contracts.md").exists()
    assert (SKILL / "scripts" / "validate_child_contract.py").exists()


def test_repo_skill_covers_current_worker_choices() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    architecture = (SKILL / "references" / "architecture-patterns.md").read_text(
        encoding="utf-8"
    )
    enterprise = (SKILL / "references" / "enterprise-openhands.md").read_text(
        encoding="utf-8"
    )
    assert "one worker implementation" in skill_text
    assert "Both Enterprise and Agent Canvas support ACP-backed profiles" in skill_text
    assert "Choose A Worker Implementation" in architecture
    assert "Coding-agent CLI" in architecture
    assert "ACP profile" in architecture
    assert "agent_profile_id" in enterprise
    assert "First-class conversation creation does not guarantee isolation" in enterprise
    assert "resend_mode=all" in enterprise
    assert "null sandbox tombstone" in enterprise


def test_sdk_example_uses_current_acp_secret_handoff() -> None:
    text = (ROOT / "shared_workspace.py").read_text(encoding="utf-8")
    assert "acp_env=" not in text
    assert 'secrets={"ANTHROPIC_API_KEY"' in text
    assert 'secrets={"GEMINI_API_KEY"' in text
    assert "DelegateTool" not in text
    assert "TaskToolSet" in text


def test_child_contract_validator_accepts_and_gates_valid_report() -> None:
    validator = load_module(SKILL / "scripts" / "validate_child_contract.py")
    result = validator.validate(
        "story-to-pr",
        "\n".join(
            [
                "status: done",
                "branch: feature/example",
                "pr: https://example.test/pr/1",
                "next_gate: code-review",
            ]
        ),
    )
    assert result["valid"] is True
    assert result["gate_allowed"] is True


def test_child_contract_validator_rejects_conflicting_status() -> None:
    validator = load_module(SKILL / "scripts" / "validate_child_contract.py")
    result = validator.validate(
        "qa",
        "status: pass\nstatus: failed\nnext_gate: human-review\n",
    )
    assert result["valid"] is False
    assert result["gate_allowed"] is False
