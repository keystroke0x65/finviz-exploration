"""Content safety checks applied before anything is written.

Secrets are hard errors. Instruction-like text is a warning: memory is data the
agent consults, never a place for commands that override the user.
"""
from __future__ import annotations

import re
from typing import List

SECRET_PATTERNS = [
    (r"\bsk-[A-Za-z0-9_-]{16,}", "API key (sk-...)"),
    (r"\b(sk|rk)_(live|test)_[A-Za-z0-9]{10,}", "secret key (sk_live/sk_test)"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key"),
    (r"\bgh[pousr]_[A-Za-z0-9]{30,}", "GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}", "GitHub token"),
    (r"\bxox[abprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}", "JWT"),
    (r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@/]{3,}@", "credentials in URL"),
    (r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?[^\s'\"]{6,}", "inline credential"),
]
INSTRUCTION_PATTERNS = [
    r"(?i)ignore (all |any )?(previous|prior|above) instructions",
    r"(?i)\bsystem prompt\b",
    r"(?i)you (must|should) always (obey|follow|comply)",
    r"(?i)do not tell the user",
]


def secret_findings(text: str) -> List[str]:
    return [label for pat, label in SECRET_PATTERNS if re.search(pat, text)]


def instruction_findings(text: str) -> List[str]:
    return [pat for pat in INSTRUCTION_PATTERNS if re.search(pat, text)]
