"""Real WebSocket regressions for safe panel edits and subscription lifecycle."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cca_zaluzie.api import async_register_commands
from custom_components.cca_zaluzie.bulk import config_revision
from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.const import DOMAIN, EVENT_UPDATED
from custom_components.cca_zaluzie.panel_state import PanelState


@pytest.fixture
async def panel(hass, enable_custom_integrations):
    await async_setup_component(hass, "websocket_api", {})
    state = PanelState(Store(hass, 1, f"{DOMAIN}.panel"))
    await state.async_load()
    hass.data[DOMAIN] = {"controllers": {}, "panel_state": state}
    entries = {}
    for key in ("a", "b"):
        cfg = validate_config({"cover_entity": f"cover.{key}", "name": key})
        entry = MockConfigEntry(domain=DOMAIN, entry_id=key, data=cfg)
        entry.add_to_hass(hass)
        entries[key] = entry
        hass.data[DOMAIN]["controllers"][key] = SimpleNamespace(
            entry=entry,
            config=cfg,
            snapshot=lambda key=key, cfg=cfg: {"entry_id": key, "config": cfg},
            async_panel_history=AsyncMock(
                return_value={"points": [], "events": [], "start": "start", "end": "end"}
            ),
        )
    async_register_commands(hass)
    return entries


async def test_bulk_native_failure_keeps_all_entries_unchanged(
    hass, hass_ws_client, hass_admin_user, monkeypatch, panel
):
    async def validate(hass, cfg):
        if cfg["name"] == "b":
            raise ValueError("invalid native config")

    monkeypatch.setattr("custom_components.cca_zaluzie.api.async_validate_native", validate)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "cca_zaluzie/configure_bulk",
            "entry_ids": ["a", "b"],
            "patch": {"debug": True},
            "revisions": {key: config_revision(entry.data) for key, entry in panel.items()},
        }
    )
    result = await client.receive_json()
    assert result["success"] is False
    assert all(not entry.options for entry in panel.values())


async def test_bulk_success_preserves_identity_and_rejects_immediate_stale_save(
    hass, hass_ws_client, hass_admin_user, panel
):
    client = await hass_ws_client(hass)
    request = {
        "id": 1,
        "type": "cca_zaluzie/configure_bulk",
        "entry_ids": ["a", "b"],
        "patch": {"debug": True},
        "revisions": {key: config_revision(entry.data) for key, entry in panel.items()},
    }
    await client.send_json(request)
    result = await client.receive_json()
    assert result["success"] is True
    assert result["result"]["configs"]["a"]["cover_entity"] == "cover.a"
    assert result["result"]["configs"]["b"]["cover_entity"] == "cover.b"
    assert result["result"]["config_revisions"] == {
        key: config_revision(cfg) for key, cfg in result["result"]["configs"].items()
    }
    await client.send_json({**request, "id": 2, "patch": {"debug": False}})
    result = await client.receive_json()
    assert result["success"] is False
    assert all(entry.options["debug"] for entry in panel.values())


async def test_subscription_distinguishes_reload_removal_and_order_only(
    hass, hass_ws_client, hass_admin_user, panel
):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "cca_zaluzie/subscribe"})
    assert (await client.receive_json())["success"]
    hass.data[DOMAIN]["controllers"].pop("a")
    hass.bus.async_fire(EVENT_UPDATED, {"entry_id": "a"})
    result = await client.receive_json()
    assert result["event"] == {"entry_id": "a", "controller": None, "removed": False}
    hass.bus.async_fire(EVENT_UPDATED, {"entry_id": "a", "removed": True})
    assert (await client.receive_json())["event"]["removed"] is True
    hass.bus.async_fire(EVENT_UPDATED, {"order": ["b"], "order_revision": 0})
    assert (await client.receive_json())["event"] == {"order": ["b"], "order_revision": 0}


async def test_reorder_revision_and_history_contract(hass, hass_ws_client, hass_admin_user, panel):
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "cca_zaluzie/reorder", "entry_ids": ["b", "a"], "revision": 0}
    )
    result = await client.receive_json()
    assert result["result"] == {"order": ["b", "a"], "order_revision": 1}
    await client.send_json(
        {"id": 2, "type": "cca_zaluzie/reorder", "entry_ids": ["a", "b"], "revision": 0}
    )
    assert (await client.receive_json())["success"] is False
    await client.send_json({"id": 3, "type": "cca_zaluzie/history", "entry_id": "a", "hours": 168})
    assert (await client.receive_json())["result"] == {
        "points": [],
        "events": [],
        "start": "start",
        "end": "end",
    }
    hass.data[DOMAIN]["controllers"]["a"].async_panel_history.assert_awaited_once_with(168)


async def test_single_config_optional_revision_and_metadata(
    hass, hass_ws_client, hass_admin_user, panel
):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "cca_zaluzie/list"})
    result = (await client.receive_json())["result"]
    assert result["fields"]["debug"]["bulk_editable"] is True
    assert result["fields"]["enabled"]["bulk_editable"] is False
    assert result["controllers"][0]["config_revision"] == config_revision(panel["a"].data)
    await client.send_json(
        {
            "id": 2,
            "type": "cca_zaluzie/configure",
            "entry_id": "a",
            "config": {**panel["a"].data, "debug": True},
            "expected_revision": "outdated",
        }
    )
    assert (await client.receive_json())["success"] is False
    assert not panel["a"].options


@pytest.mark.parametrize(
    "payload",
    [
        {
            "type": "cca_zaluzie/configure_bulk",
            "entry_ids": ["a"],
            "patch": {"debug": True},
            "revisions": {"a": "hash"},
        },
        {"type": "cca_zaluzie/reorder", "entry_ids": ["a", "b"], "revision": 0},
        {"type": "cca_zaluzie/history", "entry_id": "a", "hours": 24},
    ],
)
async def test_new_endpoints_require_admin(
    hass, hass_ws_client, hass_read_only_access_token, panel, payload
):
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json({"id": 1, **payload})
    result = await client.receive_json()
    assert result["success"] is False
    assert result["error"]["code"] == "unauthorized"


async def test_last_controller_unload_preserves_sidebar_during_reload(hass, monkeypatch, panel):
    from unittest.mock import MagicMock

    from custom_components.cca_zaluzie import async_unload_entry

    removed = MagicMock()
    monkeypatch.setattr("homeassistant.components.frontend.async_remove_panel", removed)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True))
    hass.data[DOMAIN]["panel_registered"] = True
    hass.data[DOMAIN]["controllers"] = {"a": object()}
    panel["a"].runtime_data = SimpleNamespace(async_stop=AsyncMock())
    assert await async_unload_entry(hass, panel["a"])
    assert hass.data[DOMAIN]["controllers"] == {}
    assert hass.data[DOMAIN]["panel_registered"] is True
    removed.assert_not_called()


@pytest.mark.parametrize("last_entry", [False, True])
async def test_sidebar_removed_only_when_final_config_entry_is_deleted(
    hass, monkeypatch, panel, last_entry
):
    from unittest.mock import MagicMock

    from custom_components.cca_zaluzie import async_remove_entry

    removed = MagicMock()
    monkeypatch.setattr("homeassistant.components.frontend.async_remove_panel", removed)
    hass.data[DOMAIN]["panel_registered"] = True
    # The HA fixture also calls async_entries() without a domain during shutdown.
    # Restore the real manager before fixture teardown, including on assertion failure.
    with monkeypatch.context() as entries_patch:
        entries_patch.setattr(
            hass.config_entries,
            "async_entries",
            lambda domain=None: [panel["a"]] if last_entry else list(panel.values()),
        )
        await async_remove_entry(hass, panel["a"])
    await hass.async_block_till_done()
    assert removed.call_count == int(last_entry)
    assert hass.data[DOMAIN]["panel_registered"] is not last_entry
