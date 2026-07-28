#!/usr/bin/env python3
"""Validate a delegated child's final response without external packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CELL_RULES = {
    "story-to-pr": {
        "required": {"status", "next_gate", "branch", "pr"},
        "allowed": {
            "status": {"done", "needs-human", "failed"},
            "next_gate": {"code-review", "human-review", "stop"},
        },
    },
    "code-review": {
        "required": {"status", "blocking", "next_gate"},
        "allowed": {
            "status": {"pass", "findings", "needs-human", "failed"},
            "blocking": {"yes", "no"},
            "next_gate": {"qa", "human-review", "stop"},
        },
    },
    "qa": {
        "required": {"status", "next_gate"},
        "allowed": {
            "status": {"pass", "needs-human", "failed"},
            "next_gate": {"human-review", "stop"},
        },
    },
}


def parse_fields(text: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip().lower().replace("_", "-")
        value = value.strip()
        if key not in {"status", "blocking", "artifact", "branch", "pr", "next-gate"}:
            continue
        key = key.replace("-", "_")
        if key in fields and fields[key] != value:
            errors.append(f"conflicting values for {key}")
            continue
        fields[key] = value
    return fields, errors


def validate(cell: str, text: str) -> dict[str, object]:
    rules = CELL_RULES[cell]
    fields, errors = parse_fields(text)
    normalized = {key: value.lower() for key, value in fields.items()}

    for key in sorted(rules["required"] - fields.keys()):
        errors.append(f"missing required field: {key}")

    for key, allowed in rules["allowed"].items():
        value = normalized.get(key)
        if value is not None and value not in allowed:
            errors.append(f"invalid {key}: {value}")

    gate_allowed = False
    if not errors:
        if cell == "story-to-pr":
            gate_allowed = normalized["status"] == "done" and normalized["next_gate"] == "code-review"
        elif cell == "code-review":
            gate_allowed = (
                normalized["status"] in {"pass", "findings"}
                and normalized["blocking"] == "no"
                and normalized["next_gate"] == "qa"
            )
        elif cell == "qa":
            gate_allowed = normalized["status"] == "pass" and normalized["next_gate"] == "human-review"

    return {
        "cell": cell,
        "valid": not errors,
        "gate_allowed": gate_allowed,
        "fields": fields,
        "errors": errors,
    }


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell", required=True, choices=sorted(CELL_RULES))
    parser.add_argument("response", help="final-response file, or - for stdin")
    args = parser.parse_args()

    result = validate(args.cell, read_text(args.response))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
