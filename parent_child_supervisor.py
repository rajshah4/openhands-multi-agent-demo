#!/usr/bin/env python3
"""Parent-child supervisor workflow pattern.

This is a local, dependency-free teaching example. It shows the deterministic
loop used by a parent conversation:

1. render one bounded child prompt
2. start or simulate a child conversation
3. capture a compact final response
4. gate before moving to the next child
5. write a lifecycle report

Replace `run_child` with OpenHands Cloud/Enterprise conversation API calls when
adapting this for a live workflow.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CELLS = ("story-to-pr", "code-review", "qa")
CONTINUE_STATUSES = {
    "story-to-pr": {"done"},
    "code-review": {"pass", "findings"},
    "qa": {"pass"},
}


@dataclass(frozen=True)
class ChildResult:
    name: str
    status: str
    artifact: str
    summary: str
    next_gate: str
    conversation_url: str


def parse_status_override(raw: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError("--status must be CELL=STATUS")
        cell, status = item.split("=", 1)
        overrides[cell.strip()] = status.strip()
    return overrides


def render_child_prompt(
    cell: str,
    run_id: str,
    request: str,
    prior_summary: str,
    artifact: str,
) -> str:
    return "\n".join(
        [
            f"# {cell} work cell",
            "",
            f"Run id: {run_id}",
            f"Request: {request}",
            "",
            "Prior child summary:",
            prior_summary or "none",
            "",
            "Human authority:",
            "- Do not merge, deploy, mutate secrets, or approve your own work.",
            "",
            "Final response contract:",
            f"status: <status for {cell}>",
            f"artifact: {artifact}",
            "summary: <five or fewer bullets>",
            "next_gate: <next-cell-or-stop>",
            "",
        ]
    )


def default_status(cell: str) -> str:
    return {"story-to-pr": "done", "code-review": "pass", "qa": "pass"}.get(cell, "done")


def run_child(cell: str, run_id: str, status: str, artifact: str) -> ChildResult:
    next_gate = {
        "story-to-pr": "code-review",
        "code-review": "qa",
        "qa": "human-review",
    }.get(cell, "stop")
    return ChildResult(
        name=cell,
        status=status,
        artifact=artifact,
        summary=f"Simulated {cell} completed with status `{status}`.",
        next_gate=next_gate,
        conversation_url=f"https://openhands.example/conversations/{run_id}-{cell}",
    )


def write_report(run_dir: Path, request: str, results: list[ChildResult]) -> None:
    lines = [
        "# Parent-Child Lifecycle Report",
        "",
        f"- Request: {request}",
        f"- Run directory: `{run_dir}`",
        "",
        "| Cell | Status | Conversation | Artifact |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| `{result.name}` | {result.status} | {result.conversation_url} | `{result.artifact}` |"
        )
    lines.extend(["", "## Gate Decisions", ""])
    for result in results:
        lines.append(f"- `{result.name}` -> `{result.next_gate}` because status was `{result.status}`.")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "lifecycle-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", default="Build a small, reviewable feature")
    parser.add_argument("--run-id", default=time.strftime("parent-child-%Y%m%d-%H%M%S"))
    parser.add_argument("--run-root", type=Path, default=Path("factory_runs"))
    parser.add_argument("--cells", nargs="+", default=list(DEFAULT_CELLS))
    parser.add_argument(
        "--status",
        action="append",
        default=[],
        help="override a simulated child status, for example --status code-review=needs-human",
    )
    args = parser.parse_args()

    overrides = parse_status_override(args.status)
    run_dir = args.run_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    prior_summary = ""
    results: list[ChildResult] = []
    for cell in args.cells:
        artifact = (run_dir / f"{cell}.final.md").as_posix()
        prompt = render_child_prompt(cell, args.run_id, args.request, prior_summary, artifact)
        (run_dir / f"{cell}.prompt.md").write_text(prompt, encoding="utf-8")

        result = run_child(cell, args.run_id, overrides.get(cell, default_status(cell)), artifact)
        results.append(result)
        (run_dir / f"{cell}.final.md").write_text(
            "\n".join(
                [
                    f"status: {result.status}",
                    f"artifact: {result.artifact}",
                    f"summary: {result.summary}",
                    f"next_gate: {result.next_gate}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (run_dir / "children.json").write_text(
            json.dumps([result.__dict__ for result in results], indent=2) + "\n",
            encoding="utf-8",
        )

        prior_summary += f"\n\n{cell}: {result.status} - {result.summary}"
        if result.status not in CONTINUE_STATUSES.get(cell, {"done"}):
            break

    write_report(run_dir, args.request, results)
    print(json.dumps({"run_dir": str(run_dir), "children": [r.__dict__ for r in results]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
