import pytest

def test_settings_default_hides_short_setups(api_client):
    assert api_client.get("/api/settings").json() == {"show_short_setups": False}


def test_settings_round_trip(api_client):
    api_client.put("/api/settings", json={"show_short_setups": True})

    assert api_client.get("/api/settings").json() == {"show_short_setups": True}


def test_settings_reject_non_boolean(api_client):
    assert api_client.put("/api/settings", json={"show_short_setups": "yes please"}).status_code == 422


WIDTHS_URL = "/api/settings/screen-column-widths"


def test_screen_column_widths_default_to_automatic(api_client):
    assert api_client.get(WIDTHS_URL).json() == {"widths": {}}


def test_screen_column_widths_are_saved(api_client):
    response = api_client.put(WIDTHS_URL, json={"widths": {"ticker": 180, "news": 320}})

    assert response.json() == {"widths": {"ticker": 180, "news": 320}}
    assert api_client.get(WIDTHS_URL).json() == {"widths": {"ticker": 180, "news": 320}}


def test_saving_no_widths_goes_back_to_automatic(api_client):
    api_client.put(WIDTHS_URL, json={"widths": {"ticker": 180}})
    api_client.put(WIDTHS_URL, json={"widths": {}})

    assert api_client.get(WIDTHS_URL).json() == {"widths": {}}


@pytest.mark.parametrize(
    "widths",
    [
        {"ticker": 10},                                # narrower than any column can usefully be
        {"ticker": 5000},                              # wider than any screen
        {"ticker": "wide"},
        {"Ticker; DROP": 100},                         # not a column key
        {f"column_{index}": 100 for index in range(41)},  # more columns than any table has
    ],
)
def test_screen_column_widths_reject_bad_input(api_client, widths):
    assert api_client.put(WIDTHS_URL, json={"widths": widths}).status_code == 422
