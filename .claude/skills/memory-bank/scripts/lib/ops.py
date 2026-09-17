"""Deterministic operation engine (ACE: non-LLM merge of curator deltas).

The agent never edits entry files directly. It emits a batch:

    {
      "note": "what this batch records",
      "feedback":   [{"id": "auth-0001", "tag": "helpful"}],
      "operations": [{"op": "ADD_ROOT", ...}, ...]
    }

Operations are applied in order to an in-memory copy. If any operation fails
validation, nothing is written (atomic batch).
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import budget
from .entry import Entry
from .safety import instruction_findings, secret_findings
from .search import similarity
from .store import FileStore, MemoryFile, Section, now_iso, prefix_for, today

OPS = {"ADD_ROOT", "ADD_DELTA", "UPDATE", "SUPERSEDE", "DELETE", "PROMOTE"}
TAGS = {"helpful", "harmful", "neutral"}
ENTRY_FILE_HINT = "context/<project-brief|architecture|tech-stack|conventions|decisions>.md, progress.md, or experience/<topic>.md"


class BatchError(Exception):
    pass


def _batch_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"b-{stamp}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"


class Engine:
    def __init__(self, store: FileStore, templates_dir: Path):
        self.store = store
        self.templates_dir = templates_dir
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.results: List[str] = []
        self.archive: List[str] = []
        self.refs: Dict[str, str] = {}
        self.batch_id = _batch_id()

    # ---- helpers ----------------------------------------------------
    def _err(self, i: int, msg: str) -> None:
        self.errors.append(f"op[{i}]: {msg}")

    def _warn(self, i: int, msg: str) -> None:
        self.warnings.append(f"op[{i}]: {msg}")

    def _resolve(self, ident: Optional[str]) -> Optional[str]:
        if ident and ident.startswith("@"):
            return self.refs.get(ident[1:])
        return ident

    def _check_text(self, i: int, op: dict, content: str, when: str = "") -> bool:
        ok = True
        if not isinstance(content, str) or "\n" in content:
            self._err(i, "content must be a single-line string")
            return False
        n = len(content.strip())
        if n < budget.CONTENT_MIN or n > budget.CONTENT_MAX:
            self._err(i, f"content length {n} outside {budget.CONTENT_MIN}-{budget.CONTENT_MAX} chars; split or tighten it")
            ok = False
        if when and (len(when) > budget.WHEN_MAX or "\n" in when or " :: " in when):
            self._err(i, f"when must be one line, <= {budget.WHEN_MAX} chars, without ' :: '")
            ok = False
        blob = " ".join([content, when, op.get("source", "") or "", " ".join(op.get("labels", []) or [])])
        found = secret_findings(blob)
        if found:
            self._err(i, f"possible secret ({', '.join(found)}); memory must never store credentials — describe where the secret lives instead")
            ok = False
        if instruction_findings(blob):
            self._warn(i, "content reads like an instruction to the agent; store facts and lessons, not commands")
        return ok

    def _labels(self, i: int, op: dict) -> List[str]:
        labels = op.get("labels", []) or []
        if not isinstance(labels, list):
            self._err(i, "labels must be a list")
            return []
        clean = []
        for l in labels:
            l = str(l).strip().lower().replace(" ", "-")
            if l and "," not in l and l not in clean:
                clean.append(l)
        return clean[:6]

    def _template_for(self, relpath: str) -> str:
        if relpath.startswith("experience/"):
            topic = Path(relpath).stem
            text = (self.templates_dir / "experience" / "_topic.md").read_text()
            return text.replace("{{topic}}", topic)
        p = self.templates_dir / relpath
        return p.read_text() if p.exists() else f"# {Path(relpath).stem}\n"

    def _duplicate(self, mf: MemoryFile, content: str, skip: Tuple[str, ...] = ()) -> Optional[Entry]:
        best, best_e = 0.0, None
        for _, e in mf.entries():
            if e.id in skip:
                continue
            s = similarity(content, e.content)
            if s > best:
                best, best_e = s, e
        return best_e if best >= budget.DUPLICATE_THRESHOLD else None

    def _archive(self, op: str, entries: List[Entry], reason: str, relpath: str) -> None:
        for e in entries:
            self.archive.append(
                f"- {today()} {op} batch={self.batch_id} file={relpath} reason=\"{reason.replace(chr(34), chr(39))}\"\n  {e.to_line().strip()}"
            )

    def _locate(self, i: int, ident: str) -> Optional[Tuple[MemoryFile, Section, Entry]]:
        rid = self._resolve(ident)
        if not rid:
            self._err(i, f"unknown reference {ident}")
            return None
        hit = self.store.find(rid)
        if not hit:
            self._err(i, f"entry {rid} not found (already archived, or wrong id?)")
        return hit

    # ---- feedback ---------------------------------------------------
    def feedback(self, items: List[dict]) -> None:
        for j, fb in enumerate(items or []):
            tag, ident = fb.get("tag"), fb.get("id")
            if tag not in TAGS:
                self.errors.append(f"feedback[{j}]: tag must be one of {sorted(TAGS)}")
                continue
            hit = self.store.find(ident or "")
            if not hit:
                self.errors.append(f"feedback[{j}]: entry {ident} not found")
                continue
            mf, _, e = hit
            if tag == "helpful":
                e.helpful += 1
            elif tag == "harmful":
                e.harmful += 1
            if tag != "neutral":
                self.store.mark_dirty(mf.relpath)
                self.results.append(f"{tag} +1 -> {e.id} (h={e.helpful} x={e.harmful})")

    # ---- operations -------------------------------------------------
    def apply(self, i: int, op: dict) -> None:
        kind = op.get("op")
        if kind not in OPS:
            self._err(i, f"op must be one of {sorted(OPS)}")
            return
        getattr(self, "_" + kind.lower())(i, op)

    def _add_root(self, i: int, op: dict) -> None:
        relpath = (op.get("file") or "").strip().lstrip("./")
        prefix = prefix_for(relpath)
        if not prefix:
            self._err(i, f"file '{relpath}' cannot hold entries; use {ENTRY_FILE_HINT}")
            return
        section_name = (op.get("section") or "").strip()
        if not section_name:
            self._err(i, "section is required")
            return
        kind = op.get("kind", "root")
        if kind not in ("root", "trap"):
            self._err(i, "kind must be 'root' or 'trap'")
            return
        content = (op.get("content") or "").strip()
        if not self._check_text(i, op, content):
            return
        mf = self.store.load(relpath, template=self._template_for(relpath))
        dup = self._duplicate(mf, content)
        if dup and not op.get("force"):
            self._err(i, f"near-duplicate of {dup.id} ('{dup.content[:80]}'); use UPDATE or ADD_DELTA, or set force=true with a reason")
            return
        section = mf.section(section_name)
        if section is None:
            self._warn(i, f"section '{section_name}' did not exist in {relpath}; created it")
            section = mf.section(section_name, create=True)
        e = Entry(id=self.store.next_id(prefix), kind=kind, content=content, date=today(),
                  labels=self._labels(i, op), source=(op.get("source") or "").strip())
        mf.insert(section, e)
        self.store.mark_dirty(relpath)
        if op.get("ref"):
            self.refs[op["ref"]] = e.id
        self.results.append(f"ADD_ROOT {e.id} ({kind}) -> {relpath} ## {section.name}")

    def _add_delta(self, i: int, op: dict) -> None:
        hit = self._locate(i, op.get("parent", ""))
        if not hit:
            return
        mf, section, parent = hit
        if parent.depth + 1 > budget.MAX_DELTA_DEPTH:
            self._err(i, f"{parent.id} is already at max depth {budget.MAX_DELTA_DEPTH}; PROMOTE it first or attach to a shallower node")
            return
        content = (op.get("content") or "").strip()
        when = (op.get("when") or "").strip()
        if not when:
            self._err(i, "ADD_DELTA requires 'when': the specific condition under which this variation applies")
            return
        if not self._check_text(i, op, content, when):
            return
        for x in mf.subtree(section, parent.root_id):
            if similarity(content, x.content) >= budget.DUPLICATE_THRESHOLD and not op.get("force"):
                self._err(i, f"delta repeats {x.id}; a delta must add only what the chain does not already say")
                return
        e = Entry(id=self.store.next_delta_id(mf, parent.id), kind="delta", content=content, date=today(),
                  labels=self._labels(i, op), when=when, source=(op.get("source") or "").strip())
        mf.insert(section, e)
        self.store.mark_dirty(mf.relpath)
        if op.get("ref"):
            self.refs[op["ref"]] = e.id
        self.results.append(f"ADD_DELTA {e.id} under {parent.id} when=\"{when}\"")

    def _update(self, i: int, op: dict) -> None:
        hit = self._locate(i, op.get("id", ""))
        if not hit:
            return
        mf, section, e = hit
        if not (op.get("reason") or "").strip():
            self._err(i, "UPDATE requires a reason")
            return
        changed = []
        if "content" in op:
            content = (op.get("content") or "").strip()
            if not self._check_text(i, op, content, op.get("when", e.when) or ""):
                return
            if similarity(content, e.content) < 0.35:
                self._warn(i, f"{e.id}: new content differs a lot from old; if the fact changed, SUPERSEDE keeps history")
            dup = self._duplicate(mf, content, skip=(e.id,))
            if dup and not op.get("force"):
                self._err(i, f"updated content would duplicate {dup.id}")
                return
            e.content = content
            changed.append("content")
        if "when" in op:
            if e.kind != "delta":
                self._err(i, "only deltas have 'when'")
                return
            e.when = (op.get("when") or "").strip()
            changed.append("when")
        if "labels" in op:
            e.labels = self._labels(i, op)
            changed.append("labels")
        if op.get("section"):
            if e.depth > 0:
                self._err(i, "only roots/traps can move sections; deltas stay with their parent")
                return
            if op["section"].strip().lower() != section.name.lower():
                moved = mf.remove_subtree(section, e.id)
                target = mf.section(op["section"].strip(), create=True)
                for m in moved:
                    mf.insert(target, m)
                changed.append(f"section->{target.name}")
        if not changed:
            self._err(i, "UPDATE changed nothing (give content, when, labels, or section)")
            return
        self.store.mark_dirty(mf.relpath)
        self.results.append(f"UPDATE {e.id}: {', '.join(changed)}")

    def _supersede(self, i: int, op: dict) -> None:
        hit = self._locate(i, op.get("id", ""))
        if not hit:
            return
        mf, section, old = hit
        reason = (op.get("reason") or "").strip()
        content = (op.get("content") or "").strip()
        if not reason:
            self._err(i, "SUPERSEDE requires a reason (what changed)")
            return
        if not self._check_text(i, op, content, op.get("when", old.when) or ""):
            return
        removed = mf.remove_subtree(section, old.id)
        if len(removed) > 1:
            self._warn(i, f"archived {len(removed) - 1} delta(s) under {old.id}; re-add any that still apply")
        self._archive("SUPERSEDE", removed, reason, mf.relpath)
        if old.depth == 0:
            new_id = self.store.next_id(old.prefix)
        else:
            new_id = self.store.next_delta_id(mf, old.parent_id)
        labels = self._labels(i, op) if "labels" in op else old.labels
        new = Entry(id=new_id, kind=old.kind, content=content, date=today(), labels=labels,
                    when=(op.get("when") or old.when), source=(op.get("source") or old.source), supersedes=old.id)
        mf.insert(section, new)
        self.store.mark_dirty(mf.relpath)
        if op.get("ref"):
            self.refs[op["ref"]] = new.id
        self.results.append(f"SUPERSEDE {old.id} -> {new.id}")

    def _delete(self, i: int, op: dict) -> None:
        hit = self._locate(i, op.get("id", ""))
        if not hit:
            return
        mf, section, e = hit
        reason = (op.get("reason") or "").strip()
        if not reason:
            self._err(i, "DELETE requires a reason")
            return
        removed = mf.remove_subtree(section, e.id)
        self._archive("DELETE", removed, reason, mf.relpath)
        self.store.mark_dirty(mf.relpath)
        self.results.append(f"DELETE {e.id}" + (f" (+{len(removed) - 1} deltas)" if len(removed) > 1 else ""))

    def _promote(self, i: int, op: dict) -> None:
        hit = self._locate(i, op.get("id", ""))
        if not hit:
            return
        mf, section, d = hit
        if d.depth == 0:
            self._err(i, f"{d.id} is already a root; PROMOTE takes a delta")
            return
        if any(x.id != d.id for x in mf.subtree(section, d.id)):
            self._err(i, f"{d.id} has child deltas; promote the deepest one, or DELETE/merge children first")
            return
        content = (op.get("content") or "").strip()
        if not self._check_text(i, op, content):
            return
        target = mf.section(op.get("section") or section.name, create=True)
        mf.remove_subtree(section, d.id)
        self._archive("PROMOTE", [d], op.get("reason") or "consolidated into new root", mf.relpath)
        new = Entry(id=self.store.next_id(d.prefix), kind="root", content=content, date=today(),
                    labels=self._labels(i, op) if "labels" in op else d.labels, promoted_from=d.id,
                    helpful=d.helpful, source=d.source)
        mf.insert(target, new)
        self.store.mark_dirty(mf.relpath)
        if op.get("ref"):
            self.refs[op["ref"]] = new.id
        self.results.append(f"PROMOTE {d.id} -> {new.id} (self-contained root)")


def run_batch(store: FileStore, templates_dir: Path, batch: dict, dry_run: bool = False) -> Engine:
    if not isinstance(batch, dict):
        raise BatchError("batch must be a JSON object with 'operations' and optional 'feedback' and 'note'")
    eng = Engine(store, templates_dir)
    eng.feedback(batch.get("feedback", []))
    ops = batch.get("operations", [])
    if not isinstance(ops, list):
        raise BatchError("'operations' must be a list")
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            eng._err(i, "operation must be an object")
            continue
        eng.apply(i, op)
    if not ops and not batch.get("feedback"):
        eng.warnings.append("empty batch: nothing to record")
    if eng.errors or dry_run:
        return eng
    record = {
        "batch": eng.batch_id, "ts": now_iso(), "note": batch.get("note", ""),
        "feedback": batch.get("feedback", []), "operations": ops, "results": eng.results,
    }
    eng.touched = store.commit(eng.batch_id, eng.archive, record)
    return eng
