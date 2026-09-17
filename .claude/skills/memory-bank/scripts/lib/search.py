"""Retrieval and similarity.

Today: dependency-free keyword scoring. The public functions `similarity` and
`search` are the seam for a future embedding backend — keep their signatures.

Retrieval follows DeltaMem: find the best-matching nodes, penalise failure-prone
ones, and return the full root -> delta chain so the agent sees the base
experience plus the variation that applies.
"""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from .entry import Entry
from .store import FileStore, MemoryFile, Section

STOPWORDS = set(
    "a an the and or but if then else of to in on at by for with from into over under is are was were be been "
    "it its this that these those as not no do does did can could should would will may might must use using "
    "when where what which who how why all any some each more most other such only own same so than too very "
    "just also via per vs etc i we you they he she them our your their".split()
)


def tokens(text: str) -> List[str]:
    out = []
    for t in re.findall(r"[a-z0-9][a-z0-9_.-]*", text.lower()):
        t = t.strip(".-_")
        if len(t) < 2 or t in STOPWORDS:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def similarity(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jac, seq)


def _score(entry: Entry, section: Section, mf: MemoryFile, q: List[str]) -> float:
    fields = [
        (tokens(entry.content), 1.0),
        (tokens(" ".join(entry.labels)), 2.0),
        (tokens(entry.when), 1.5),
        (tokens(section.name + " " + mf.relpath.replace("/", " ").replace(".md", "")), 0.5),
    ]
    score = 0.0
    for qt in set(q):
        best = 0.0
        for toks, w in fields:
            if qt in toks:
                best = max(best, w)
            elif any(t.startswith(qt) or qt.startswith(t) for t in toks if len(t) > 3 and len(qt) > 3):
                best = max(best, w * 0.5)
        score += best
    if score == 0:
        return 0.0
    score /= math.sqrt(len(set(q)))
    score += 0.05 * min(entry.helpful, 5)
    if entry.harmful > entry.helpful:
        score *= 0.5  # DeltaMem failure penalty / ACE harmful counter
    return score


def excluded(entry: Entry) -> bool:
    return entry.harmful >= 2 and entry.harmful > entry.helpful


def search(store: FileStore, query: str, limit: int = 6, include_harmful: bool = False,
           scope: str = "all") -> List[Dict]:
    q = tokens(query)
    if not q:
        return []
    scored: List[Tuple[float, MemoryFile, Section, Entry]] = []
    for mf in store.all_files():
        if scope == "context" and not mf.relpath.startswith("context/"):
            continue
        if scope == "experience" and not mf.relpath.startswith("experience/"):
            continue
        for s, e in mf.entries():
            if not include_harmful and excluded(e):
                continue
            sc = _score(e, s, mf, q)
            if sc > 0:
                scored.append((sc, mf, s, e))
    scored.sort(key=lambda t: -t[0])
    if scored:  # drop weak incidental matches relative to the best hit
        floor = max(0.3, scored[0][0] * 0.35)
        scored = [t for t in scored if t[0] >= floor]

    groups: Dict[str, Dict] = {}
    for sc, mf, s, e in scored:
        key = e.root_id
        if key not in groups:
            if len(groups) >= limit:
                continue
            groups[key] = {"file": mf.relpath, "section": s.name, "score": 0.0, "matched": set(), "mf": mf, "s": s}
        g = groups[key]
        g["score"] = max(g["score"], sc)
        g["matched"].add(e.id)

    results = []
    for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["score"]):
        mf, s = g["mf"], g["s"]
        subtree = mf.subtree(s, key)
        by_id = {x.id: x for x in subtree}
        keep = set()
        for mid in g["matched"]:
            parts = mid.split(".")
            for i in range(1, len(parts) + 1):  # root -> ... -> match chain
                keep.add(".".join(parts[:i]))
        chain = [x for x in subtree if x.id in keep and (include_harmful or not excluded(x))]
        other = [x for x in subtree if x.id not in keep and x.depth > 0 and (include_harmful or not excluded(x))]
        results.append({
            "file": g["file"], "section": g["section"], "score": round(g["score"], 3),
            "chain": chain, "matched": sorted(g["matched"]), "other_deltas": other,
            "root_present": key in by_id,
        })
    return results
