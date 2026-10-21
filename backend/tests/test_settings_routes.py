def test_settings_default_hides_short_setups(api_client):
    assert api_client.get("/api/settings").json() == {"show_short_setups": False}


def test_settings_round_trip(api_client):
    api_client.put("/api/settings", json={"show_short_setups": True})

    assert api_client.get("/api/settings").json() == {"show_short_setups": True}


def test_settings_reject_non_boolean(api_client):
    assert api_client.put("/api/settings", json={"show_short_setups": "yes please"}).status_code == 422
