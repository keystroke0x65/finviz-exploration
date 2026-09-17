"""Storage layer.

Everything that touches disk lives here, behind the FileStore class. A future
backend (SQLite, vector store, hosted memory service) should implement the same
public methods so ops.py, search.py and memory.py keep working unchanged.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, Union

from .entry import Entry, looks_like_entry

CONTEXT_FILES = {
    "context/project-brief.md": "brief",
    "context/architecture.md": "arch",
    "context/tech-stack.md": "stack",
    "context/conventions.md": "conv",
    "context/decisions.md": "dec",
    "progress.md": "prog",
}
RESERVED_PREFIXES = set(CONTEXT_FILES.values())
TOPIC_RE = re.compile(r"^experience/([a-z][a-z0-9-]{1,30})\.md$")
STATE_FILE = ".state.json"
LOG_FILE = "ops-log.jsonl"
ARCHIVE_FILE = "history/archive.md"
SNAPSHOT_DIR = ".snapshots"
MAX_SNAPSHOTS = 20

Line = Union[str, Entry]


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prefix_for(relpath: str) -> Optional[str]:
    """ID prefix for an entry file, or None if the path may not hold entries."""
    if relpath in CONTEXT_FILES:
        return CONTEXT_FILES[relpath]
    m = TOPIC_RE.match(relpath)
    if m and m.group(1) not in RESERVED_PREFIXES:
        return m.group(1)
    return None


@dataclass
class Section:
    name: str
    lines: List[Line] = field(default_factory=list)

    def entries(self) -> List[Entry]:
        return [l for l in self.lines if isinstance(l, Entry)]


@dataclass
class MemoryFile:
    relpath: str
    preamble: List[str] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    bad_lines: List[Tuple[int, str]] = field(default_factory=list)

    @classmethod
    def parse(cls, relpath: str, text: str) -> "MemoryFile":
        mf = cls(relpath)
        current: Optional[Section] = None
        for n, raw in enumerate(text.splitlines(), 1):
            if raw.startswith("## "):
                current = Section(raw[3:].strip())
                mf.sections.append(current)
                continue
            if current is None:
                mf.preamble.append(raw)
                continue
            if looks_like_entry(raw):
                e = Entry.parse(raw)
                if e is None:
                    mf.bad_lines.append((n, raw))
                    current.lines.append(raw)
                else:
                    current.lines.append(e)
            else:
                current.lines.append(raw)
        return mf

    def render(self) -> str:
        out = list(self.preamble)
        for s in self.sections:
            if out and out[-1].strip():
                out.append("")
            out.append(f"## {s.name}")
            body = [l.to_line() if isinstance(l, Entry) else l for l in s.lines]
            while body and not body[-1].strip():
                body.pop()
            out.extend(body)
        return "\n".join(out).rstrip() + "\n"

    # ---- lookup -----------------------------------------------------
    def entries(self) -> Iterator[Tuple[Section, Entry]]:
        for s in self.sections:
            for e in s.entries():
                yield s, e

    def find(self, entry_id: str) -> Optional[Tuple[Section, Entry]]:
        for s, e in self.entries():
            if e.id == entry_id:
                return s, e
        return None

    def section(self, name: str, create: bool = False) -> Optional[Section]:
        for s in self.sections:
            if s.name.lower() == name.lower():
                return s
        if create:
            s = Section(name)
            self.sections.append(s)
            return s
        return None

    # ---- mutation ---------------------------------------------------
    def subtree(self, section: Section, entry_id: str) -> List[Entry]:
        return [e for e in section.entries() if e.id == entry_id or e.id.startswith(entry_id + ".")]

    def remove_subtree(self, section: Section, entry_id: str) -> List[Entry]:
        removed = self.subtree(section, entry_id)
        ids = {e.id for e in removed}
        section.lines = [l for l in section.lines if not (isinstance(l, Entry) and l.id in ids)]
        return removed

    def insert(self, section: Section, entry: Entry) -> None:
        """Roots go to the end of the section; deltas go after their parent's subtree."""
        if entry.parent_id:
            idx = None
            for i, l in enumerate(section.lines):
                if isinstance(l, Entry) and (l.id == entry.parent_id or l.id.startswith(entry.parent_id + ".")):
                    idx = i
            if idx is not None:
                section.lines.insert(idx + 1, entry)
                return
        last = max((i for i, l in enumerate(section.lines) if isinstance(l, Entry)), default=None)
        if last is None:
            while section.lines and isinstance(section.lines[-1], str) and not section.lines[-1].strip():
                section.lines.pop()
            section.lines.append(entry)
        else:
            section.lines.insert(last + 1, entry)


class FileStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._files: Dict[str, MemoryFile] = {}
        self._dirty: set = set()
        self._created: set = set()
        self.state = self._load_state()

    # ---- discovery --------------------------------------------------
    @staticmethod
    def locate(explicit: Optional[str] = None) -> Optional[Path]:
        if explicit:
            p = Path(explicit)
            return p if (p / STATE_FILE).exists() else None
        env = os.environ.get("MEMORY_BANK_DIR")
        if env and (Path(env) / STATE_FILE).exists():
            return Path(env)
        base = Path.cwd()
        for d in [base, *base.parents]:
            cand = d / "memory-bank"
            if (cand / STATE_FILE).exists():
                return cand
        return None

    # ---- state ------------------------------------------------------
    def _load_state(self) -> dict:
        p = self.root / STATE_FILE
        if p.exists():
            try:
                return json.loads(p.read_text())
            except json.JSONDecodeError:
                pass
        return {"version": 1, "counters": {}, "reminded_sessions": []}

    def save_state(self) -> None:
        (self.root / STATE_FILE).write_text(json.dumps(self.state, indent=2) + "\n")

    # ---- files ------------------------------------------------------
    def entry_paths(self) -> List[str]:
        paths = [p for p in CONTEXT_FILES if (self.root / p).exists()]
        exp = self.root / "experience"
        if exp.is_dir():
            for f in sorted(exp.glob("*.md")):
                rel = f"experience/{f.name}"
                if prefix_for(rel):
                    paths.append(rel)
        for rel in self._files:
            if rel not in paths:
                paths.append(rel)
        return paths

    def load(self, relpath: str, template: Optional[str] = None) -> Optional[MemoryFile]:
        if relpath in self._files:
            return self._files[relpath]
        p = self.root / relpath
        if p.exists():
            mf = MemoryFile.parse(relpath, p.read_text())
        elif template is not None:
            mf = MemoryFile.parse(relpath, template)
            self._created.add(relpath)
            self._dirty.add(relpath)
        else:
            return None
        self._files[relpath] = mf
        return mf

    def all_files(self) -> List[MemoryFile]:
        return [mf for p in self.entry_paths() if (mf := self.load(p)) is not None]

    def find(self, entry_id: str) -> Optional[Tuple[MemoryFile, Section, Entry]]:
        for mf in self.all_files():
            hit = mf.find(entry_id)
            if hit:
                return mf, hit[0], hit[1]
        return None

    def mark_dirty(self, relpath: str) -> None:
        self._dirty.add(relpath)

    def next_id(self, prefix: str) -> str:
        highest = self.state["counters"].get(prefix, 0)
        for mf in self.all_files():
            for _, e in mf.entries():
                if e.prefix == prefix:
                    highest = max(highest, int(e.root_id.rsplit("-", 1)[1]))
        highest = max(highest, self._archived_max(prefix))
        self.state["counters"][prefix] = highest + 1
        return f"{prefix}-{highest + 1:04d}"

    def next_delta_id(self, mf: MemoryFile, parent_id: str) -> str:
        n = 0
        pattern = re.compile(re.escape(parent_id) + r"\.(\d+)")
        candidates = [e.id for _, e in mf.entries()] + self._archived_ids()
        for i in candidates:
            m = pattern.fullmatch(i)
            if m:
                n = max(n, int(m.group(1)))
        return f"{parent_id}.{n + 1}"

    def _archive_text(self) -> str:
        p = self.root / ARCHIVE_FILE
        return p.read_text() if p.exists() else ""

    def _archived_ids(self) -> List[str]:
        return re.findall(r"- \[([^\]]+)\]", self._archive_text())

    def _archived_max(self, prefix: str) -> int:
        best = 0
        for i in self._archived_ids():
            m = re.fullmatch(re.escape(prefix) + r"-(\d{4})(\.\d+)*", i)
            if m:
                best = max(best, int(m.group(1)))
        return best

    # ---- writes -----------------------------------------------------
    def commit(self, batch_id: str, archive_lines: List[str], log_record: dict) -> List[str]:
        touched = sorted(self._dirty)
        snap = self.root / SNAPSHOT_DIR / batch_id
        snap.mkdir(parents=True, exist_ok=True)
        manifest = {"created": [], "modified": []}
        extra = [ARCHIVE_FILE] if archive_lines else []
        for rel in touched + extra:
            src = self.root / rel
            if src.exists():
                dst = snap / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                manifest["modified"].append(rel)
            else:
                manifest["created"].append(rel)
        (snap / "manifest.json").write_text(json.dumps(manifest, indent=2))

        for rel in touched:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self._files[rel].render())
        if archive_lines:
            ap = self.root / ARCHIVE_FILE
            ap.parent.mkdir(parents=True, exist_ok=True)
            head = "" if ap.exists() else "# Archive\n\nSuperseded, deleted and promoted entries. Not loaded by default.\n\n"
            with ap.open("a") as fh:
                fh.write(head + "\n".join(archive_lines) + "\n")
        self.append_log(log_record)
        self.state["batches"] = self.state.get("batches", 0) + 1
        self.save_state()
        self._prune_snapshots()
        self._dirty.clear()
        self._created.clear()
        return touched + extra

    def append_log(self, record: dict) -> None:
        with (self.root / LOG_FILE).open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_log(self) -> List[dict]:
        p = self.root / LOG_FILE
        if not p.exists():
            return []
        out = []
        for line in p.read_text().splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def _prune_snapshots(self) -> None:
        d = self.root / SNAPSHOT_DIR
        if not d.is_dir():
            return
        snaps = sorted(p for p in d.iterdir() if p.is_dir())
        for old in snaps[:-MAX_SNAPSHOTS]:
            shutil.rmtree(old, ignore_errors=True)

    def rollback_last(self) -> Tuple[Optional[str], List[str]]:
        log = self.read_log()
        undone = {r["rollback_of"] for r in log if "rollback_of" in r}
        for rec in reversed(log):
            bid = rec.get("batch")
            if not bid or "rollback_of" in rec or bid in undone:
                continue
            snap = self.root / SNAPSHOT_DIR / bid
            if not (snap / "manifest.json").exists():
                return None, [f"no snapshot for {bid}; cannot roll back further"]
            manifest = json.loads((snap / "manifest.json").read_text())
            for rel in manifest["modified"]:
                shutil.copy2(snap / rel, self.root / rel)
            for rel in manifest["created"]:
                p = self.root / rel
                if p.exists():
                    p.unlink()
            self.append_log({"batch": f"rb-{bid}", "ts": now_iso(), "rollback_of": bid})
            shutil.rmtree(snap, ignore_errors=True)
            return bid, manifest["modified"] + manifest["created"]
        return None, ["nothing to roll back"]
