"""Maps the screen form's human-readable fields to Finviz filter codes and back.

Only the filters the user screens with day to day are on the form; any other
Finviz code (there are hundreds) round-trips untouched as an "extra" code.
"""

from dataclasses import dataclass, replace
from typing import Literal

MarketCapOption = Literal[
    "large_and_under", "mid_and_under", "small_and_under", "micro_and_under", "nano"
]

COUNTRY_CODES = {"usa": "geo_usa"}

# Finviz market cap bands: large < $200B, mid < $10B, small < $2B,
# micro < $300M, nano < $50M.
MARKET_CAP_CODES: dict[str, str] = {
    "large_and_under": "cap_largeunder",
    "mid_and_under": "cap_midunder",
    "small_and_under": "cap_smallunder",
    "micro_and_under": "cap_microunder",
    "nano": "cap_nano",
}

# Numeric form fields: (field name, Finviz code prefix, allowed values).
NUMERIC_FIELDS: list[tuple[str, str, list[float]]] = [
    ("price_under", "sh_price_u", [1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50]),
    ("float_under_millions", "sh_float_u", [1, 5, 10, 20, 50, 100]),
    ("volume_over_thousands", "sh_curvol_o", [100, 200, 500, 1000, 2000, 5000, 10000]),
    ("relative_volume_over", "sh_relvol_o", [1, 1.5, 2, 3, 5, 10]),
]

FORM_OPTIONS: dict[str, list] = {
    "country": list(COUNTRY_CODES),
    "market_cap": list(MARKET_CAP_CODES),
    **{name: options for name, _, options in NUMERIC_FIELDS},
}

SIGNAL_OPTIONS = {
    "ta_topgainers": "Top gainers",
    "ta_toplosers": "Top losers",
    "ta_newhigh": "New high",
    "ta_unusualvolume": "Unusual volume",
    "ta_mostactive": "Most active",
}


class InvalidFormValueError(ValueError):
    """Raised when a form field holds a value the form doesn't offer."""


@dataclass(frozen=True)
class ScreenForm:
    country: Literal["usa"] | None = None
    price_under: float | None = None
    float_under_millions: float | None = None
    market_cap: MarketCapOption | None = None
    volume_over_thousands: int | None = None
    relative_volume_over: float | None = None


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _require_option(field_name: str, value: object) -> None:
    if value not in FORM_OPTIONS[field_name]:
        raise InvalidFormValueError(
            f"{field_name}={value!r} is not one of {FORM_OPTIONS[field_name]}"
        )


# Code order follows the form's field order, so a saved screen's codes read
# the same way the form shows them.
FORM_FIELD_ORDER = [
    "country",
    "price_under",
    "float_under_millions",
    "market_cap",
    "volume_over_thousands",
    "relative_volume_over",
]

NUMERIC_PREFIXES = {name: prefix for name, prefix, _ in NUMERIC_FIELDS}


def _code_for_field(field_name: str, value: object) -> str:
    _require_option(field_name, value)
    if field_name == "country":
        return COUNTRY_CODES[value]
    if field_name == "market_cap":
        return MARKET_CAP_CODES[value]
    return f"{NUMERIC_PREFIXES[field_name]}{_format_number(value)}"


def form_to_codes(form: ScreenForm) -> list[str]:
    return [
        _code_for_field(field_name, getattr(form, field_name))
        for field_name in FORM_FIELD_ORDER
        if getattr(form, field_name) is not None
    ]


def _match_code(code: str) -> tuple[str, object] | None:
    for country, country_code in COUNTRY_CODES.items():
        if code == country_code:
            return "country", country
    for market_cap, market_cap_code in MARKET_CAP_CODES.items():
        if code == market_cap_code:
            return "market_cap", market_cap
    for field_name, prefix, options in NUMERIC_FIELDS:
        if not code.startswith(prefix):
            continue
        try:
            value = float(code.removeprefix(prefix))
        except ValueError:
            return None
        if value in options:
            return field_name, int(value) if value.is_integer() else value
    return None


def codes_to_form(codes: list[str]) -> tuple[ScreenForm, list[str]]:
    form = ScreenForm()
    unknown_codes: list[str] = []
    filled_fields: set[str] = set()
    for code in codes:
        match = _match_code(code)
        if match is None or match[0] in filled_fields:
            unknown_codes.append(code)
            continue
        field_name, value = match
        form = replace(form, **{field_name: value})
        filled_fields.add(field_name)
    return form, unknown_codes

