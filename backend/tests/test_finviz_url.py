import pytest

from app.screens.finviz_url import (
    MAX_FILTER_CODES,
    MAX_URL_LENGTH,
    InvalidScreenerUrlError,
    ScreenCriteria,
    build_finviz_screener_url,
    parse_finviz_screener_url,
)


def test_parse_extracts_filters_signal_order():
    url = (
        "https://elite.finviz.com/screener.ashx?v=111"
        "&f=geo_usa,sh_price_u20,sh_float_u10&s=ta_topgainers&o=-change"
    )

    assert parse_finviz_screener_url(url) == ScreenCriteria(
        ["geo_usa", "sh_price_u20", "sh_float_u10"], "ta_topgainers", "-change"
    )


def test_parse_accepts_finviz_com_without_elite():
    criteria = parse_finviz_screener_url("https://finviz.com/screener.ashx?v=111&f=geo_usa")

    assert criteria == ScreenCriteria(["geo_usa"], None, None)


def test_parse_handles_url_encoded_commas():
    criteria = parse_finviz_screener_url(
        "https://finviz.com/screener.ashx?f=geo_usa%2Csh_price_u20"
    )

    assert criteria.filters == ["geo_usa", "sh_price_u20"]


def test_parse_returns_empty_filters_when_f_missing():
    criteria = parse_finviz_screener_url("https://finviz.com/screener.ashx?v=111&s=ta_topgainers")

    assert criteria == ScreenCriteria([], "ta_topgainers", None)


def test_parse_trims_surrounding_whitespace():
    criteria = parse_finviz_screener_url("  https://finviz.com/screener.ashx?f=geo_usa \n")

    assert criteria.filters == ["geo_usa"]


def test_parse_rejects_non_finviz_host():
    with pytest.raises(InvalidScreenerUrlError):
        parse_finviz_screener_url("https://evil.example/screener.ashx?f=geo_usa")


def test_parse_rejects_lookalike_host():
    with pytest.raises(InvalidScreenerUrlError):
        parse_finviz_screener_url("https://finviz.com.evil.example/screener.ashx?f=geo_usa")


def test_parse_rejects_non_screener_path():
    with pytest.raises(InvalidScreenerUrlError):
        parse_finviz_screener_url("https://finviz.com/quote.ashx?t=AAPL")


def test_parse_rejects_non_url_text():
    with pytest.raises(InvalidScreenerUrlError):
        parse_finviz_screener_url("geo_usa,sh_price_u20")


def test_parse_rejects_oversized_url():
    url = "https://finviz.com/screener.ashx?f=" + "a" * MAX_URL_LENGTH

    with pytest.raises(InvalidScreenerUrlError, match="too long"):
        parse_finviz_screener_url(url)


def test_parse_rejects_too_many_codes():
    codes = ",".join(f"code_{index}" for index in range(MAX_FILTER_CODES + 1))

    with pytest.raises(InvalidScreenerUrlError, match="too many"):
        parse_finviz_screener_url(f"https://finviz.com/screener.ashx?f={codes}")


def test_parse_rejects_codes_with_bad_characters():
    with pytest.raises(InvalidScreenerUrlError):
        parse_finviz_screener_url("https://finviz.com/screener.ashx?f=geo_usa,<script>")


def test_build_url_round_trips_through_parse():
    criteria = ScreenCriteria(["geo_usa", "sh_relvol_o1.5"], "ta_topgainers", "-change")

    url = build_finviz_screener_url(criteria)

    assert url.startswith("https://elite.finviz.com/screener.ashx?v=111&f=geo_usa,sh_relvol_o1.5")
    assert parse_finviz_screener_url(url) == criteria


def test_build_url_omits_missing_signal_and_order():
    url = build_finviz_screener_url(ScreenCriteria(["geo_usa"], None, None))

    assert url == "https://elite.finviz.com/screener.ashx?v=111&f=geo_usa"
