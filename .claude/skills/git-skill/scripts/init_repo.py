#!/usr/bin/env python3
"""Initialize a git repository with a stack-aware .gitignore and a safe initial commit.

Usage:
  python3 init_repo.py [path] [--branch main] [--dry-run] [--no-commit] [--allow-nested]

Refuses to run in unsafe locations (/, home dir, system dirs) or inside an
existing repository (unless --allow-nested). Prints a JSON summary.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from detect_repo import detect_stacks, is_unsafe_location  # noqa: E402

LARGE_FILE_BYTES = 50 * 1024 * 1024

GITIGNORE = {
    "base": [
        "# OS", ".DS_Store", "Thumbs.db", "desktop.ini",
        "# Editors", ".idea/", ".vscode/*", "!.vscode/settings.json",
        "!.vscode/extensions.json", "*.swp", "*~",
        "# Env & secrets", ".env", ".env.*", "!.env.example", "*.pem", "*.key",
        "# Logs", "*.log",
    ],
    "node": [
        "# Node", "node_modules/", "npm-debug.log*", "yarn-debug.log*",
        "yarn-error.log*", "pnpm-debug.log*", ".pnpm-store/", "coverage/",
        "dist/", "*.tsbuildinfo",
    ],
    "nextjs": ["# Next.js", ".next/", "out/", "next-env.d.ts", ".vercel/"],
    "astro": ["# Astro", ".astro/", "dist/"],
    "python": [
        "# Python", "__pycache__/", "*.py[cod]", ".venv/", "venv/", "env/",
        "*.egg-info/", "build/", "dist/", ".pytest_cache/", ".mypy_cache/",
        ".ruff_cache/", ".ipynb_checkpoints/",
    ],
    "rust": ["# Rust", "target/"],
    "go": ["# Go", "bin/", "*.test", "*.out"],
    "docker": ["# Docker", "docker-compose.override.yml"],
    "chrome-extension": ["# Extension builds", "*.crx", "*.zip"],
}

# Always-ignored directories we skip when scanning for large/sensitive files
SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "venv", "target", "dist", "__pycache__"}


def git(args, cwd, check=True):
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


def build_gitignore_lines(stacks):
    lines, seen = [], set()
    for key in ["base", *stacks]:
        for line in GITIGNORE.get(key, []):
            if line.startswith("#") or line not in seen:
                lines.append(line)
                seen.add(line)
    return lines


def merge_gitignore(path: Path, lines, dry_run):
    gi = path / ".gitignore"
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    existing_set = {l.strip() for l in existing}
    to_add, pending_comment = [], None
    for line in lines:
        if line.startswith("#"):
            pending_comment = line
            continue
        if line not in existing_set:
            if pending_comment:
                to_add.append(pending_comment)
                pending_comment = None
            to_add.append(line)
    if to_add and not dry_run:
        with gi.open("a", encoding="utf-8") as fh:
            if existing and existing[-1].strip():
                fh.write("\n")
            fh.write("\n".join(to_add) + "\n")
    return [l for l in to_add if not l.startswith("#")], gi.exists() or bool(to_add)


def scan_large_files(path: Path):
    large = []
    for p in path.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(path).parts):
            continue
        try:
            if p.is_file() and p.stat().st_size > LARGE_FILE_BYTES:
                large.append({"file": str(p.relative_to(path)), "bytes": p.stat().st_size})
        except OSError:
            continue
    return large


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--allow-nested", action="store_true")
    ap.add_argument("--message", default="chore: initial commit")
    args = ap.parse_args()

    path = Path(args.path).expanduser().resolve()
    out = {"path": str(path), "dry_run": args.dry_run, "warnings": []}

    def finish(code=0):
        print(json.dumps(out, indent=2))
        sys.exit(code)

    if not path.is_dir():
        out["error"] = "path is not a directory"
        finish(1)
    if is_unsafe_location(path):
        out["error"] = "refusing to init in an unsafe location (root, home, or system dir); pick a project folder"
        finish(1)

    probe = git(["rev-parse", "--show-toplevel"], path, check=False)
    if probe.returncode == 0:
        root = Path(probe.stdout.strip()).resolve()
        if root == path:
            out["error"] = "already a git repository"
            finish(1)
        if not args.allow_nested:
            out["error"] = f"folder is inside an existing repository at {root}; rerun with --allow-nested to create a separate repo"
            finish(1)
        out["warnings"].append(f"creating a nested repo inside {root}; add this folder to the parent's .gitignore or use a submodule")

    stacks = detect_stacks(path)
    out["detected_stacks"] = stacks
    out["branch"] = args.branch

    # 1. init
    if not args.dry_run:
        r = git(["init", "-b", args.branch], path, check=False)
        if r.returncode != 0:  # git < 2.28 has no -b
            git(["init"], path)
            git(["symbolic-ref", "HEAD", f"refs/heads/{args.branch}"], path)

    # 2. .gitignore
    added, _ = merge_gitignore(path, build_gitignore_lines(stacks), args.dry_run)
    out["gitignore_lines_added"] = added

    # 3. large files
    large = scan_large_files(path)
    if large:
        out["warnings"].append("large files found (>50 MB); consider Git LFS or ignoring them")
        out["large_files"] = large

    if args.dry_run:
        out["next"] = "rerun without --dry-run to initialize"
        finish(0)

    # 4. stage
    git(["add", "-A"], path)
    staged = git(["diff", "--cached", "--name-only"], path).stdout.split("\n")
    staged = [s for s in staged if s]
    out["files_staged"] = len(staged)

    # 5. secret check
    check = subprocess.run([sys.executable, str(SCRIPT_DIR / "check_staged.py"), str(path)],
                           capture_output=True, text=True)
    try:
        check_result = json.loads(check.stdout)
    except ValueError:
        check_result = {"clean": False, "findings": [{"issue": "secret check failed to run"}]}
    out["secret_check"] = check_result

    if not check_result.get("clean", False):
        out["committed"] = False
        out["reason"] = "secret check found issues; files left staged. Unstage/ignore them, then commit."
        finish(0)

    if args.no_commit:
        out["committed"] = False
        out["reason"] = "--no-commit set; files left staged"
        finish(0)

    name = git(["config", "user.name"], path, check=False).stdout.strip()
    email = git(["config", "user.email"], path, check=False).stdout.strip()
    if not (name and email):
        out["committed"] = False
        out["reason"] = ("git identity not configured; ask the user to run "
                         "git config --global user.name \"Name\" and git config --global user.email \"email\"")
        finish(0)

    if not staged:
        out["committed"] = False
        out["reason"] = "nothing to commit (empty folder)"
        finish(0)

    git(["commit", "-m", args.message], path)
    out["committed"] = True
    out["commit"] = git(["log", "-1", "--format=%h %s"], path).stdout.strip()
    finish(0)


if __name__ == "__main__":
    main()
