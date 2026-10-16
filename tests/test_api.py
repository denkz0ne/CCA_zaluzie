"""Permission and configuration boundaries of the panel API."""

import pytest

pytest.importorskip("homeassistant")

from homeassistant.setup import async_setup_component

from custom_components.cca_zaluzie.api import async_register_commands
from custom_components.cca_zaluzie.const import DOMAIN


@pytest.fixture(autouse=True)
async def api(hass, enable_custom_integrations):
    await async_setup_component(hass, "websocket_api", {})
    hass.data[DOMAIN] = {"controllers": {}}
    async_register_commands(hass)


async def test_admin_reads_controller_metadata(hass, hass_ws_client, hass_admin_user):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "cca_zaluzie/list"})
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["controllers"] == []
    assert response["result"]["fields"]["open_position"]["maximum"] == 100


async def test_nonadmin_cannot_control_a_cover(hass, hass_ws_client, hass_read_only_access_token):
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json(
        {"id": 1, "type": "cca_zaluzie/control", "entry_id": "anything", "action": "close"}
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unauthorized"


async def test_missing_controller_returns_visible_error(hass, hass_ws_client, hass_admin_user):
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "cca_zaluzie/control", "entry_id": "gone", "action": "close"}
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"


async def test_prediction_api_is_read_only_and_returns_selected_range(
    hass, hass_ws_client, hass_admin_user
):
    class Controller:
        async def async_predict(self, start_date, days, *, from_now=False):
            return {"start_date": start_date, "days": days, "from_now": from_now, "events": []}

    hass.data[DOMAIN]["controllers"]["entry"] = Controller()
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "cca_zaluzie/predict",
            "entry_id": "entry",
            "start_date": "2026-10-20",
            "days": 3,
        }
    )
    response = await client.receive_json()

    assert response["success"] is True
    assert response["result"] == {
        "start_date": "2026-10-20",
        "days": 3,
        "from_now": False,
        "events": [],
    }


async def test_prediction_api_can_start_from_current_time(hass, hass_ws_client):
    class Controller:
        async def async_predict(self, start_date, days, *, from_now=False):
            return {"start_date": start_date, "days": days, "from_now": from_now, "events": []}

    hass.data[DOMAIN]["controllers"]["entry"] = Controller()
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "cca_zaluzie/predict",
            "entry_id": "entry",
            "days": 2,
            "from_now": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["from_now"] is True


async def test_nonadmin_cannot_request_prediction(hass, hass_ws_client, hass_read_only_access_token):
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json(
        {
            "id": 1,
            "type": "cca_zaluzie/predict",
            "entry_id": "anything",
            "start_date": "2026-10-20",
        }
    )
    response = await client.receive_json()

    assert response["success"] is False
    assert response["error"]["code"] == "unauthorized"
