#!/usr/bin/env python3
"""Scan staged files for likely secrets and oversized files before committing.

Usage: python3 check_staged.py [path]
Exit code 0 = clean, 1 = findings (details printed as JSON), 2 = error.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

MAX_FILE_BYTES = 50 * 1024 * 1024  # GitHub rejects files over 100 MB and warns above 50 MB

SENSITIVE_NAMES = [
    re.compile(r"(^|/)\.env(\.[\w-]+)?$"),          # .env, .env.local, .env.production
    re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$"),
    re.compile(r"\.(pem|key|p12|pfx|keystore|jks)$"),
    re.compile(r"(^|/)credentials(\.json)?$"),
    re.compile(r"(^|/)service[-_]?account.*\.json$"),
    re.compile(r"(^|/)\.npmrc$"),
    re.compile(r"(^|/)\.pypirc$"),
]
# Template files that are meant to be committed
ALLOWED_NAMES = re.compile(r"\.env\.(example|sample|template)$")

SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    "openai_key": re.compile(r"\bsk-(proj-)?[A-Za-z0-9_-]{32,}"),
    "stripe_or_clerk_secret": re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{20,}"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "db_url_with_password": re.compile(r"\b(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^\s:/@]+:[^\s@/]{6,}@"),
}


def git(args, cwd):
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip())
    return proc.stdout


def main():
    cwd = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    try:
        names = git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], cwd)
    except (RuntimeError, OSError) as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)

    files = [n for n in names.decode(errors="replace").split("\0") if n]
    findings = []

    for f in files:
        if not ALLOWED_NAMES.search(f) and any(p.search(f) for p in SENSITIVE_NAMES):
            findings.append({"file": f, "issue": "sensitive_filename"})
            continue

        try:
            size = int(git(["cat-file", "-s", f":{f}"], cwd).strip())
        except (RuntimeError, ValueError):
            continue
        if size > MAX_FILE_BYTES:
            findings.append({"file": f, "issue": "large_file", "bytes": size})
            continue
        if size > 2 * 1024 * 1024:
            continue  # skip scanning big blobs for patterns

        try:
            content = git(["show", f":{f}"], cwd)
        except RuntimeError:
            continue
        if b"\0" in content[:8000]:
            continue  # binary
        text = content.decode(errors="replace")
        for label, pattern in SECRET_PATTERNS.items():
            m = pattern.search(text)
            if m:
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append({"file": f, "issue": label, "line": line_no})

    result = {"files_checked": len(files), "clean": not findings, "findings": findings}
    print(json.dumps(result, indent=2))
    sys.exit(0 if not findings else 1)


if __name__ == "__main__":
    main()
