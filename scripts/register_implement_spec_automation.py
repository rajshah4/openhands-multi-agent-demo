#!/usr/bin/env python3
"""Register the implement-approved-spec prompt automation on OpenHands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "automations" / "implement-approved-spec" / "automation.prompt-preset.json"


def load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key.replace("_", "").isalnum():
            os.environ.setdefault(key, value.strip().strip("'").strip('"'))


def expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}
    return value


def load_payload() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    prompt = (SPEC_PATH.parent / spec["prompt_file"]).read_text(encoding="utf-8")
    payload: dict[str, Any] = {
        "name": expand_env(spec["name"]),
        "prompt": prompt,
        "trigger": expand_env(spec["trigger"]),
    }
    for field in ("timeout", "keep_alive", "repos", "model"):
        if field in spec:
            payload[field] = expand_env(spec[field])
    return payload


def post_prompt_preset(host: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        host.rstrip("/") + "/api/automation/v1/preset/prompt",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenHands API returned {exc.code}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--host", default="https://app.replicated.rajistics.com")
    parser.add_argument("--repository", default="rajshah4/openhands-multi-agent-demo")
    parser.add_argument(
        "--repo-url",
        default="https://github.com/rajshah4/openhands-multi-agent-demo",
    )
    parser.add_argument("--ref", default="main")
    args = parser.parse_args()

    if args.env_file:
        load_env_file(args.env_file)
    os.environ["IMPLEMENT_SPEC_REPOSITORY"] = args.repository
    os.environ["IMPLEMENT_SPEC_REPO_URL"] = args.repo_url
    os.environ["IMPLEMENT_SPEC_REF"] = args.ref

    payload = load_payload()
    if not args.apply:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    api_key = (
        os.getenv("OPENHANDS_API_KEY_ORG")
        or os.getenv("OPENHANDS_API_KEY_RAJISTICS")
        or os.getenv("OPENHANDS_API_KEY")
    )
    if not api_key:
        print("An OpenHands organization API key is required for --apply.", file=sys.stderr)
        return 2

    result = post_prompt_preset(args.host, api_key, payload)
    print(
        json.dumps(
            {
                "id": result.get("id"),
                "name": result.get("name"),
                "enabled": result.get("enabled"),
                "trigger": result.get("trigger"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
