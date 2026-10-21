"""Reads and writes Finviz screener URLs, the main way the user brings a screen in."""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

MAX_URL_LENGTH = 2000
MAX_FILTER_CODES = 50
CODE_PATTERN = r"^-?[a-z0-9_.]{1,40}$"

ALLOWED_HOSTS = {"finviz.com", "www.finviz.com", "elite.finviz.com"}
SCREENER_PATH = "/screener.ashx"
SCREENER_BASE_URL = "https://elite.finviz.com/screener.ashx"
# Overview table view; only affects how Finviz displays the screen when opened.
SCREENER_VIEW = "111"

_code_regex = re.compile(CODE_PATTERN)


class InvalidScreenerUrlError(ValueError):
    """Raised when text isn't a usable Finviz screener URL."""


@dataclass(frozen=True)
class ScreenCriteria:
    filters: list[str]
    signal: str | None
    order: str | None


def is_valid_code(code: str) -> bool:
    return bool(_code_regex.match(code))


def _single_param(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if not values or not values[0]:
        return None
    return values[0]


def _validate_code(code: str, what: str) -> str:
    if not is_valid_code(code):
        raise InvalidScreenerUrlError(f"{what} {code!r} isn't a Finviz code")
    return code


def parse_finviz_screener_url(url: str) -> ScreenCriteria:
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise InvalidScreenerUrlError(f"URL is too long (max {MAX_URL_LENGTH} characters)")

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.hostname not in ALLOWED_HOSTS:
        raise InvalidScreenerUrlError("Paste a screener URL from finviz.com")
    if parts.path != SCREENER_PATH:
        raise InvalidScreenerUrlError("That's not a Finviz screener page (expected /screener.ashx)")

    query = parse_qs(parts.query)
    raw_filters = _single_param(query, "f")
    filters = [code for code in (raw_filters or "").split(",") if code]
    if len(filters) > MAX_FILTER_CODES:
        raise InvalidScreenerUrlError(f"URL has too many filters (max {MAX_FILTER_CODES})")

    signal = _single_param(query, "s")
    order = _single_param(query, "o")
    return ScreenCriteria(
        filters=[_validate_code(code, "Filter") for code in filters],
        signal=None if signal is None else _validate_code(signal, "Signal"),
        order=None if order is None else _validate_code(order, "Order"),
    )


def build_finviz_screener_url(criteria: ScreenCriteria) -> str:
    # Codes are restricted to CODE_PATTERN, so they need no URL escaping and
    # the commas stay readable.
    url = f"{SCREENER_BASE_URL}?v={SCREENER_VIEW}&f={','.join(criteria.filters)}"
    if criteria.signal:
        url += f"&s={criteria.signal}"
    if criteria.order:
        url += f"&o={criteria.order}"
    return url
