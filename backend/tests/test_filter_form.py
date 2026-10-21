import pytest

from app.screens.filter_form import (
    InvalidFormValueError,
    ScreenForm,
    codes_to_form,
    form_to_codes,
)


def test_form_to_codes_maps_user_screen():
    form = ScreenForm(country="usa", price_under=20, float_under_millions=10)

    assert form_to_codes(form) == ["geo_usa", "sh_price_u20", "sh_float_u10"]


def test_form_to_codes_maps_every_field():
    form = ScreenForm(
        country="usa",
        price_under=5,
        float_under_millions=20,
        market_cap="large_and_under",
        volume_over_thousands=1000,
        relative_volume_over=2,
    )

    assert form_to_codes(form) == [
        "geo_usa",
        "sh_price_u5",
        "sh_float_u20",
        "cap_largeunder",
        "sh_curvol_o1000",
        "sh_relvol_o2",
    ]


def test_form_to_codes_formats_fractional_relative_volume():
    assert form_to_codes(ScreenForm(relative_volume_over=1.5)) == ["sh_relvol_o1.5"]


def test_form_to_codes_returns_empty_list_for_empty_form():
    assert form_to_codes(ScreenForm()) == []


def test_form_to_codes_rejects_value_not_in_options():
    with pytest.raises(InvalidFormValueError, match="price_under"):
        form_to_codes(ScreenForm(price_under=17))


def test_codes_to_form_round_trips_known_codes():
    form = ScreenForm(
        country="usa",
        price_under=20,
        float_under_millions=10,
        market_cap="micro_and_under",
        volume_over_thousands=500,
        relative_volume_over=1.5,
    )

    assert codes_to_form(form_to_codes(form)) == (form, [])


def test_codes_to_form_returns_unknown_codes_in_order():
    codes = ["geo_usa", "ta_rsi_os30", "sh_price_u20", "fa_pe_u10"]

    assert codes_to_form(codes) == (
        ScreenForm(country="usa", price_under=20),
        ["ta_rsi_os30", "fa_pe_u10"],
    )


def test_codes_to_form_treats_value_outside_options_as_unknown():
    # Finviz has sh_price_u25-style codes the form doesn't offer; they must
    # survive as extra codes rather than be dropped or coerced.
    assert codes_to_form(["sh_price_u25"]) == (ScreenForm(), ["sh_price_u25"])
