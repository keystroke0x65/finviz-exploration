#!/usr/bin/env python3
"""Detect the git state of a folder and print it as JSON.

Usage: python3 detect_repo.py [path]

States:
  no_git   - git executable not found
  no_repo  - folder is not inside any git repository
  nested   - folder is inside a repository whose root is a parent folder
  repo     - folder is the root of a git repository
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Marker files -> stack names. Order doesn't matter; all matches are reported.
STACK_MARKERS = {
    "node": ["package.json"],
    "nextjs": ["next.config.js", "next.config.mjs", "next.config.ts"],
    "astro": ["astro.config.mjs", "astro.config.js", "astro.config.ts"],
    "python": ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
    "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml"],
    "chrome-extension": ["manifest.json"],
}


def run_git(args, cwd, strip=True):
    """Run a git command, returning (returncode, stdout)."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30
        )
        return proc.returncode, (proc.stdout.strip() if strip else proc.stdout.rstrip("\n"))
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def detect_stacks(path: Path):
    stacks = []
    for stack, markers in STACK_MARKERS.items():
        if any((path / m).exists() for m in markers):
            stacks.append(stack)
    # manifest.json alone is ambiguous; only call it an extension if it has manifest_version
    if "chrome-extension" in stacks:
        try:
            data = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            if "manifest_version" not in data:
                stacks.remove("chrome-extension")
        except (OSError, ValueError):
            stacks.remove("chrome-extension")
    return stacks


def is_unsafe_location(path: Path) -> bool:
    resolved = path.resolve()
    home = Path.home().resolve()
    unsafe = {Path("/"), home, Path("/usr"), Path("/etc"), Path("/var"),
              Path("/bin"), Path("/opt"), Path("/tmp"), Path("/System"),
              Path("/Users"), Path("/home")}
    if os.name == "nt":
        unsafe.add(Path(resolved.anchor))
    return resolved in unsafe


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser()
    result = {"path": str(path.resolve())}

    if not path.is_dir():
        result.update(state="error", error=f"not a directory: {path}")
        print(json.dumps(result, indent=2))
        sys.exit(1)

    result["unsafe_location"] = is_unsafe_location(path)
    result["detected_stacks"] = detect_stacks(path)
    result["has_gitignore"] = (path / ".gitignore").exists()

    if shutil.which("git") is None:
        result["state"] = "no_git"
        print(json.dumps(result, indent=2))
        return

    rc, version = run_git(["--version"], path)
    result["git_version"] = version

    rc, name = run_git(["config", "user.name"], path)
    rc2, email = run_git(["config", "user.email"], path)
    result["identity_configured"] = bool(name and email)

    rc, root = run_git(["rev-parse", "--show-toplevel"], path)
    if rc != 0 or not root:
        result["state"] = "no_repo"
        print(json.dumps(result, indent=2))
        return

    root_path = Path(root).resolve()
    result["repo_root"] = str(root_path)
    result["state"] = "repo" if root_path == path.resolve() else "nested"

    rc, _ = run_git(["rev-parse", "--verify", "HEAD"], path)
    result["has_commits"] = rc == 0

    rc, branch = run_git(["branch", "--show-current"], path)
    result["branch"] = branch or None  # None means detached HEAD

    rc, remotes = run_git(["remote", "-v"], path)
    remote_map = {}
    for line in remotes.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            remote_map[parts[0]] = parts[1]
    result["remotes"] = remote_map

    rc, status = run_git(["status", "--porcelain"], path, strip=False)
    lines = [l for l in status.splitlines() if l]
    result["changes"] = {
        "staged": sum(1 for l in lines if l[0] not in " ?"),
        "unstaged": sum(1 for l in lines if len(l) > 1 and l[1] not in " ?"),
        "untracked": sum(1 for l in lines if l.startswith("??")),
    }

    if branch and result["has_commits"]:
        rc, upstream = run_git(["rev-parse", "--abbrev-ref", "@{upstream}"], path)
        if rc == 0:
            result["upstream"] = upstream
            rc, counts = run_git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], path)
            if rc == 0 and counts:
                ahead, behind = counts.split()
                result["ahead"], result["behind"] = int(ahead), int(behind)
        else:
            result["upstream"] = None

    git_dir_rc, git_dir = run_git(["rev-parse", "--git-dir"], path)
    if git_dir_rc == 0:
        gd = (path / git_dir) if not Path(git_dir).is_absolute() else Path(git_dir)
        in_progress = [op for op, marker in [
            ("merge", "MERGE_HEAD"), ("rebase", "rebase-merge"),
            ("rebase", "rebase-apply"), ("cherry-pick", "CHERRY_PICK_HEAD"),
            ("revert", "REVERT_HEAD")] if (gd / marker).exists()]
        result["operation_in_progress"] = in_progress[0] if in_progress else None

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
