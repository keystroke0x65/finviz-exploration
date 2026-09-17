#!/usr/bin/env python3
"""memory-bank CLI. Python 3.8+, standard library only.

Commands
  init [PROJECT_DIR]           create memory-bank/ from templates (never overwrites)
  find QUERY... [--scope S]    retrieve root->delta chains for a task
  apply OPS.json [--dry-run]   validate and apply an operations batch (atomic)
  validate                     check format, ids, orphans, secrets, budgets
  consolidate                  report promote / prune / duplicate / stale / budget candidates
  stats                        counts and counters
  index                        regenerate memory-bank/index.md
  rollback                     undo the most recent applied batch

Global: --bank PATH (default: nearest ./memory-bank upward, or $MEMORY_BANK_DIR), --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TEMPLATES = HERE.parent / "assets" / "templates"

from lib import budget  # noqa: E402
from lib.entry import Entry  # noqa: E402
from lib.ops import BatchError, run_batch  # noqa: E402
from lib.safety import secret_findings  # noqa: E402
from lib.search import excluded, search, similarity  # noqa: E402
from lib.store import STATE_FILE, FileStore, prefix_for, today  # noqa: E402


def emit(args, data, text: str) -> None:
    print(json.dumps(data, indent=2, default=str) if args.json else text)


def open_store(args) -> FileStore:
    root = FileStore.locate(args.bank)
    if not root:
        sys.exit("No memory bank found. Run: memory.py init [PROJECT_DIR]  (or pass --bank PATH)")
    return FileStore(root)


# ---------------------------------------------------------------- init
def cmd_init(args) -> int:
    project = Path(args.project or ".").resolve()
    bank = project / "memory-bank"
    created, kept = [], []
    for src in sorted(TEMPLATES.rglob("*.md")):
        rel = src.relative_to(TEMPLATES)
        if rel.parts[0] == "experience":
            continue  # topic files are created on first ADD_ROOT
        dst = bank / rel
        if dst.exists():
            kept.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text().replace("{{project}}", project.name).replace("{{date}}", today())
        dst.write_text(text)
        created.append(str(rel))
    (bank / "experience").mkdir(exist_ok=True)
    (bank / "history").mkdir(exist_ok=True)
    gi = bank / ".gitignore"
    if not gi.exists():
        gi.write_text(".snapshots/\n")
    store = FileStore(bank)
    if not (bank / STATE_FILE).exists():
        store.state["created"] = today()
        store.save_state()
        created.append(STATE_FILE)
    write_index(store)
    emit(args, {"bank": str(bank), "created": created, "kept": kept},
         f"memory bank: {bank}\ncreated: {', '.join(created) or '-'}\nkept existing: {', '.join(kept) or '-'}\n"
         "next: follow references/init.md to fill context files via an operations batch")
    return 0


# ---------------------------------------------------------------- find
def fmt_entry(e: Entry, mark: bool = False) -> str:
    flag = " ⚠TRAP" if e.kind == "trap" else ""
    warn = " (harmful>helpful)" if e.harmful > e.helpful else ""
    star = "→ " if mark else "  "
    when = f' [when: {e.when}]' if e.when else ""
    return f"{'  ' * e.depth}{star}[{e.id}]{flag} h={e.helpful} x={e.harmful}{warn}{when} :: {e.content}"


def cmd_find(args) -> int:
    store = open_store(args)
    query = " ".join(args.query)
    results = search(store, query, limit=args.limit, include_harmful=args.include_harmful, scope=args.scope)
    if args.json:
        print(json.dumps([{**r, "chain": [e.to_line().strip() for e in r["chain"]],
                           "other_deltas": [e.to_line().strip() for e in r["other_deltas"]]} for r in results], indent=2))
        return 0
    if not results:
        print(f"no entries match '{query}'. Try broader or different keywords, or read index.md.")
        return 0
    print(f"# memory for: {query}\n# chains are root → delta; apply the deepest delta whose [when] fits. Note the IDs you rely on.\n")
    for r in results:
        print(f"## {r['file']} › {r['section']}  (score {r['score']})")
        for e in r["chain"]:
            print(fmt_entry(e, mark=e.id in r["matched"]))
        if r["other_deltas"]:
            shown = r["other_deltas"][:5]
            print("  other variations under this root:")
            for e in shown:
                print(f"    [{e.id}] when: {e.when}")
            if len(r["other_deltas"]) > 5:
                print(f"    … {len(r['other_deltas']) - 5} more")
        print()
    return 0


# ---------------------------------------------------------------- apply
def cmd_apply(args) -> int:
    store = open_store(args)
    raw = sys.stdin.read() if args.ops == "-" else Path(args.ops).read_text()
    try:
        batch = json.loads(raw)
        eng = run_batch(store, TEMPLATES, batch, dry_run=args.dry_run)
    except (json.JSONDecodeError, BatchError) as exc:
        print(f"ERROR: invalid batch: {exc}")
        return 2
    status = "error" if eng.errors else ("dry-run" if args.dry_run else "applied")
    if status == "applied":
        write_index(store)
    data = {"status": status, "batch": eng.batch_id, "results": eng.results,
            "warnings": eng.warnings, "errors": eng.errors}
    lines = [f"status: {status}" + ("" if status != "applied" else f" (batch {eng.batch_id})")]
    lines += [f"  ✓ {r}" for r in eng.results] if not eng.errors else []
    lines += [f"  ! {w}" for w in eng.warnings]
    lines += [f"  ✗ {e}" for e in eng.errors]
    if eng.errors:
        lines.append("nothing was written. Fix the operations and re-run.")
    emit(args, data, "\n".join(lines))
    return 1 if eng.errors else 0


# ---------------------------------------------------------------- validate
def collect_issues(store: FileStore):
    errors, warnings = [], []
    seen = {}
    total_chars = 0
    for mf in store.all_files():
        text = (store.root / mf.relpath).read_text() if (store.root / mf.relpath).exists() else ""
        total_chars += len(text)
        for n, raw in mf.bad_lines:
            errors.append(f"{mf.relpath}:{n}: unparseable entry line: {raw.strip()[:90]}")
        ids_here = set()
        count = 0
        for s, e in mf.entries():
            count += 1
            errors += [f"{mf.relpath}: {p}" for p in e.problems()]
            if e.id in seen:
                errors.append(f"duplicate id {e.id} in {mf.relpath} and {seen[e.id]}")
            seen[e.id] = mf.relpath
            ids_here.add(e.id)
            if prefix_for(mf.relpath) and e.prefix != prefix_for(mf.relpath):
                warnings.append(f"{mf.relpath}: {e.id} prefix does not match file (expected {prefix_for(mf.relpath)}-)")
            if e.parent_id and e.parent_id not in ids_here:
                errors.append(f"{mf.relpath}: orphan delta {e.id} (parent {e.parent_id} missing or placed after it)")
            if e.depth > budget.MAX_DELTA_DEPTH:
                errors.append(f"{mf.relpath}: {e.id} deeper than {budget.MAX_DELTA_DEPTH}")
            if secret_findings(e.content + " " + e.when + " " + e.source):
                errors.append(f"{mf.relpath}: {e.id} looks like it contains a secret — remove it")
        warnings += budget.file_warnings(mf.relpath, count, len(text))
    ac = store.root / "active-context.md"
    if ac.exists():
        n = len(ac.read_text().splitlines())
        if n > budget.ACTIVE_CONTEXT_MAX_LINES:
            warnings.append(f"active-context.md has {n} lines (budget {budget.ACTIVE_CONTEXT_MAX_LINES}); trim it")
        if secret_findings(ac.read_text()):
            errors.append("active-context.md looks like it contains a secret — remove it")
    if total_chars > budget.TOTAL_CHARS_WARN:
        warnings.append(f"entry files total {total_chars} chars (warn at {budget.TOTAL_CHARS_WARN}); consolidate")
    return errors, warnings


def cmd_validate(args) -> int:
    store = open_store(args)
    errors, warnings = collect_issues(store)
    text = "\n".join([f"✗ {e}" for e in errors] + [f"! {w}" for w in warnings]) or "ok: memory bank is valid"
    emit(args, {"errors": errors, "warnings": warnings}, text)
    return 1 if errors else 0


# ---------------------------------------------------------------- consolidate
def cmd_consolidate(args) -> int:
    store = open_store(args)
    report = {"promote": [], "prune": [], "duplicates": [], "stale": [], "done_overflow": [], "budget": []}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=budget.STALE_DAYS)).strftime("%Y-%m-%d")
    for mf in store.all_files():
        items = list(mf.entries())
        for s, e in items:
            children = [x for _, x in items if x.parent_id == e.id]
            if e.depth > 0 and e.helpful >= budget.PROMOTE_MIN_HELPFUL and e.harmful == 0 and not children:
                chain = [x for _, x in items if e.id == x.id or e.id.startswith(x.id + ".")]
                report["promote"].append({"id": e.id, "file": mf.relpath,
                                          "chain": [fmt_entry(x) for x in sorted(chain, key=lambda x: x.depth)]})
            if excluded(e):
                report["prune"].append({"id": e.id, "file": mf.relpath, "line": fmt_entry(e)})
            if e.helpful + e.harmful == 0 and e.date and e.date < cutoff and not mf.relpath.startswith("context/"):
                report["stale"].append({"id": e.id, "file": mf.relpath, "line": fmt_entry(e)})
        for a in range(len(items)):
            for b in range(a + 1, len(items)):
                ea, eb = items[a][1], items[b][1]
                if ea.root_id == eb.root_id and (ea.depth == 0 or eb.depth == 0):
                    continue
                sim = similarity(ea.content, eb.content)
                if sim >= budget.NEAR_DUPLICATE_REPORT:
                    report["duplicates"].append({"file": mf.relpath, "a": ea.id, "b": eb.id, "similarity": round(sim, 2)})
        if mf.relpath == "progress.md":
            done = mf.section("Done")
            if done and len(done.entries()) > budget.DONE_SECTION_MAX:
                report["done_overflow"] = [e.id for e in done.entries()[: len(done.entries()) - budget.DONE_SECTION_MAX]]
    _, warnings = collect_issues(store)
    report["budget"] = [w for w in warnings if "budget" in w or "consolidate" in w]
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    out = ["# consolidation report — decide, then express changes as an operations batch (see references/maintain.md)\n"]
    if report["promote"]:
        out.append("## PROMOTE candidates (delta proven helpful ≥%d times, never harmful)" % budget.PROMOTE_MIN_HELPFUL)
        for p in report["promote"]:
            out.append(f"- {p['id']} in {p['file']}:")
            out += [f"    {c}" for c in p["chain"]]
    if report["prune"]:
        out.append("\n## PRUNE candidates (harmful ≥%d and harmful > helpful)" % budget.PRUNE_MIN_HARMFUL)
        out += [f"- {p['file']}: {p['line']}" for p in report["prune"]]
    if report["duplicates"]:
        out.append("\n## near-duplicates (merge with UPDATE + DELETE, or keep if they differ meaningfully)")
        out += [f"- {d['file']}: {d['a']} ~ {d['b']} ({d['similarity']})" for d in report["duplicates"]]
    if report["stale"]:
        out.append(f"\n## never-used entries older than {budget.STALE_DAYS} days (verify still true; DELETE if not)")
        out += [f"- {s['file']}: {s['line']}" for s in report["stale"]]
    if report["done_overflow"]:
        out.append(f"\n## progress.md Done section over {budget.DONE_SECTION_MAX}; DELETE oldest: {', '.join(report['done_overflow'])}")
    if report["budget"]:
        out.append("\n## budget")
        out += [f"- {w}" for w in report["budget"]]
    if len(out) == 1:
        out.append("nothing to consolidate")
    print("\n".join(out))
    return 0


# ---------------------------------------------------------------- stats / index
def gather_stats(store: FileStore) -> dict:
    files = []
    for mf in store.all_files():
        entries = [e for _, e in mf.entries()]
        p = store.root / mf.relpath
        labels = {}
        for e in entries:
            for l in e.labels:
                labels[l] = labels.get(l, 0) + 1
        files.append({
            "file": mf.relpath, "entries": len(entries),
            "roots": sum(e.kind == "root" for e in entries), "deltas": sum(e.kind == "delta" for e in entries),
            "traps": sum(e.kind == "trap" for e in entries),
            "chars": len(p.read_text()) if p.exists() else 0,
            "sections": [s.name for s in mf.sections],
            "top_labels": [k for k, _ in sorted(labels.items(), key=lambda kv: -kv[1])[:5]],
            "last_update": max((e.date for e in entries if e.date), default=""),
        })
    return {"files": files, "batches": store.state.get("batches", 0), "created": store.state.get("created", "")}


def write_index(store: FileStore) -> None:
    st = gather_stats(store)
    lines = [
        "# Memory Bank Index",
        "",
        "<!-- Generated by memory.py. Do not edit by hand. -->",
        "",
        "Always read this file and `active-context.md` at session start. Load other files only when the task touches them,",
        "or run `memory.py find <keywords>` to pull just the relevant root → delta chains.",
        "",
        "| File | Entries (root/delta/trap) | Sections | Labels | Updated |",
        "|---|---|---|---|---|",
    ]
    for f in st["files"]:
        lines.append(f"| {f['file']} | {f['entries']} ({f['roots']}/{f['deltas']}/{f['traps']}) | "
                     f"{', '.join(f['sections'])} | {', '.join(f['top_labels'])} | {f['last_update']} |")
    lines += ["", "Also: `active-context.md` (current focus, freeform), `history/archive.md` (superseded/deleted, not loaded by default), "
              "`ops-log.jsonl` (audit trail).", "", f"Batches applied: {st['batches']}. Bank created: {st['created']}."]
    (store.root / "index.md").write_text("\n".join(lines) + "\n")


def cmd_stats(args) -> int:
    store = open_store(args)
    st = gather_stats(store)
    text = "\n".join(f"{f['file']}: {f['entries']} entries ({f['roots']} root, {f['deltas']} delta, {f['traps']} trap), {f['chars']} chars"
                     for f in st["files"]) + f"\nbatches: {st['batches']}"
    emit(args, st, text)
    return 0


def cmd_index(args) -> int:
    store = open_store(args)
    write_index(store)
    print(f"wrote {store.root / 'index.md'}")
    return 0


def cmd_rollback(args) -> int:
    store = open_store(args)
    bid, files = store.rollback_last()
    if not bid:
        print(f"rollback: {files[0]}")
        return 1
    write_index(FileStore(store.root))
    print(f"rolled back {bid}; restored: {', '.join(files)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="memory.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", help="path to memory-bank directory")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("project", nargs="?"); p.set_defaults(fn=cmd_init)
    p = sub.add_parser("find"); p.add_argument("query", nargs="+"); p.add_argument("--limit", type=int, default=6)
    p.add_argument("--scope", choices=["all", "context", "experience"], default="all")
    p.add_argument("--include-harmful", action="store_true"); p.set_defaults(fn=cmd_find)
    p = sub.add_parser("apply"); p.add_argument("ops", help="ops JSON file, or - for stdin")
    p.add_argument("--dry-run", action="store_true"); p.set_defaults(fn=cmd_apply)
    for name, fn in [("validate", cmd_validate), ("consolidate", cmd_consolidate), ("stats", cmd_stats),
                     ("index", cmd_index), ("rollback", cmd_rollback)]:
        sub.add_parser(name).set_defaults(fn=fn)
    # allow global flags after the subcommand too
    argv = list(sys.argv[1:] if argv is None else argv)
    for flag in ("--json",):
        if flag in argv:
            argv.remove(flag); argv.insert(0, flag)
    if "--bank" in argv:
        i = argv.index("--bank")
        val = argv[i:i + 2]; del argv[i:i + 2]; argv[:0] = val
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
