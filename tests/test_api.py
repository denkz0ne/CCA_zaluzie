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
