"""Entry model for memory-bank files.

Line format (one entry per line, deltas indented two spaces per depth):

    - [auth-0001] root h=2 x=0 d=2026-09-16 labels=auth,clerk src="middleware.ts" :: Content
      - [auth-0001.1] delta h=0 x=0 d=2026-09-16 when="API routes" :: Content
    - [auth-0002] trap h=0 x=0 d=2026-09-16 :: Content

h = helpful count, x = harmful count (ACE counters).
root/delta/trap mirror DeltaMem root nodes, residual nodes, and failure records.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ID_RE = re.compile(r"^[a-z][a-z0-9-]*-\d{4}(\.\d+)*$")
LINE_RE = re.compile(
    r"^(?P<indent>\s*)- \[(?P<id>[^\]]+)\]\s+(?P<kind>root|delta|trap)\s*(?P<attrs>.*?)\s::\s(?P<content>.*)$"
)
ATTR_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
KINDS = ("root", "delta", "trap")


def looks_like_entry(line: str) -> bool:
    return bool(re.match(r"^\s*- \[[^\]]*\]", line))


def _unquote(v: str) -> str:
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return v


def _quote(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class Entry:
    id: str
    kind: str
    content: str
    helpful: int = 0
    harmful: int = 0
    date: str = ""
    labels: List[str] = field(default_factory=list)
    when: str = ""
    source: str = ""
    supersedes: str = ""
    promoted_from: str = ""
    extra: Dict[str, str] = field(default_factory=dict)

    # ---- id helpers -------------------------------------------------
    @property
    def parent_id(self) -> Optional[str]:
        return self.id.rsplit(".", 1)[0] if "." in self.id else None

    @property
    def root_id(self) -> str:
        return self.id.split(".", 1)[0]

    @property
    def depth(self) -> int:
        return self.id.count(".")

    @property
    def prefix(self) -> str:
        return self.root_id.rsplit("-", 1)[0]

    # ---- serialization ---------------------------------------------
    def to_line(self) -> str:
        parts = [f"[{self.id}]", self.kind, f"h={self.helpful}", f"x={self.harmful}"]
        if self.date:
            parts.append(f"d={self.date}")
        if self.labels:
            parts.append("labels=" + ",".join(self.labels))
        if self.when:
            parts.append("when=" + _quote(self.when))
        if self.source:
            parts.append("src=" + _quote(self.source))
        if self.supersedes:
            parts.append(f"supersedes={self.supersedes}")
        if self.promoted_from:
            parts.append(f"from={self.promoted_from}")
        for k, v in self.extra.items():
            parts.append(f"{k}={_quote(v) if ' ' in v else v}")
        return "  " * self.depth + "- " + " ".join(parts) + " :: " + self.content

    @classmethod
    def parse(cls, line: str) -> Optional["Entry"]:
        m = LINE_RE.match(line.rstrip("\n"))
        if not m:
            return None
        attrs = {k: _unquote(v) for k, v in ATTR_RE.findall(m.group("attrs"))}
        known = {"h", "x", "d", "labels", "when", "src", "supersedes", "from"}
        try:
            helpful = int(attrs.get("h", "0"))
            harmful = int(attrs.get("x", "0"))
        except ValueError:
            return None
        return cls(
            id=m.group("id"),
            kind=m.group("kind"),
            content=m.group("content").strip(),
            helpful=helpful,
            harmful=harmful,
            date=attrs.get("d", ""),
            labels=[l for l in attrs.get("labels", "").split(",") if l],
            when=attrs.get("when", ""),
            source=attrs.get("src", ""),
            supersedes=attrs.get("supersedes", ""),
            promoted_from=attrs.get("from", ""),
            extra={k: v for k, v in attrs.items() if k not in known},
        )

    def problems(self) -> List[str]:
        out = []
        if not ID_RE.match(self.id):
            out.append(f"{self.id}: malformed id")
        if self.depth > 0 and self.kind != "delta":
            out.append(f"{self.id}: dotted id must have kind 'delta'")
        if self.depth == 0 and self.kind == "delta":
            out.append(f"{self.id}: kind 'delta' requires a dotted id like x-0001.1")
        if self.kind == "delta" and not self.when:
            out.append(f"{self.id}: delta is missing when=")
        return out
