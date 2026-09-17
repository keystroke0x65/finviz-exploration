#!/usr/bin/env python3
"""Agent hook entry points (designed for Claude Code hooks; see hooks/settings.example.json).

  hooks.py session-start   print index.md + active-context.md so the session starts primed
  hooks.py stop            once per session, ask the agent to run record mode before stopping
  hooks.py pre-compact     remind the agent to record before context is compacted

All commands exit 0 and do nothing when no memory bank is found, so the hooks are
safe to install globally.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib.store import FileStore  # noqa: E402

MAX_ACTIVE_CHARS = 4000
RECORD_REASON = (
    "Before stopping: use the memory-bank skill in record mode (references/reflect.md, then references/curate.md). "
    "Reflect on this session's evidence, send feedback for any memory IDs you relied on, and apply an operations batch "
    "with memory.py apply. Update active-context.md. If nothing durable was learned, say 'no memory update' and stop."
)


def read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def session_start(bank: Path) -> None:
    parts = ["[memory-bank] Project memory loaded. Use the memory-bank skill: run `memory.py find <keywords>` before tasks "
             "and record mode after meaningful work.\n"]
    for name in ("index.md", "active-context.md"):
        p = bank / name
        if p.exists():
            text = p.read_text()
            if len(text) > MAX_ACTIVE_CHARS:
                text = text[:MAX_ACTIVE_CHARS] + "\n…(truncated)"
            parts.append(f"--- {name} ---\n{text}")
    print("\n".join(parts))


def stop(bank: Path, payload: dict) -> None:
    if payload.get("stop_hook_active"):
        return  # already continuing because of this hook; never loop
    session = payload.get("session_id") or "unknown"
    store = FileStore(bank)
    seen = store.state.setdefault("reminded_sessions", [])
    if session in seen:
        return
    seen.append(session)
    store.state["reminded_sessions"] = seen[-50:]
    store.save_state()
    print(json.dumps({"decision": "block", "reason": RECORD_REASON}))


def pre_compact(bank: Path) -> None:
    print("[memory-bank] Context is about to be compacted. If this session produced durable lessons or facts, "
          "run record mode now so they are not lost.")


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = read_stdin_json()
    cwd = payload.get("cwd")
    if cwd:
        import os
        os.chdir(cwd)
    bank = FileStore.locate(None)
    if not bank:
        return 0
    if cmd == "session-start":
        session_start(bank)
    elif cmd == "stop":
        stop(bank, payload)
    elif cmd == "pre-compact":
        pre_compact(bank)
    return 0


if __name__ == "__main__":
    sys.exit(main())
