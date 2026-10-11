"""Real HA config entries, service calls and controller lifecycle."""
from datetime import timedelta

import pytest

pytest.importorskip("homeassistant")

from homeassistant.core import Context
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.const import DOMAIN


@pytest.fixture(autouse=True)
def custom(enable_custom_integrations):
    pass


@pytest.fixture
async def entry(hass, monkeypatch):
    async def register_panel(*args, **kwargs):
        pass

    monkeypatch.setattr("custom_components.cca_zaluzie.api.async_register_panel", register_panel)
    calls = []

    async def service(call):
        calls.append(call)

    for name in ("open_cover", "close_cover", "set_cover_position", "stop_cover"):
        hass.services.async_register("cover", name, service)
    hass.states.async_set("cover.blind", "open", {"current_position": 100, "supported_features": 15})
    config_entry = MockConfigEntry(domain=DOMAIN, title="Test blind", unique_id="cover.blind",
        data=validate_config({"cover_entity": "cover.blind", "name": "Test blind", "morning_enabled": False, "evening_enabled": False}))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    yield config_entry, calls
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_user_config_creates_one_entry_and_rejects_duplicate(hass):
    hass.states.async_set("cover.blind", "open", {"current_position": 100})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"cover_entity": "cover.blind", "name": "Blind", "cover_type": "blind"})
    assert result["step_id"] == "schedule"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"time_enabled": True, "morning_enabled": True, "evening_enabled": True, "morning_early": "06:30", "morning_late": "08:00", "evening_early": "18:00", "evening_late": "21:30"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data={"cover_entity": "cover.blind", "name": "Other", "cover_type": "blind"})
    assert duplicate["type"] == FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_invalid_schedule_stays_in_flow(hass):
    hass.states.async_set("cover.blind", "open")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data={"cover_entity": "cover.blind", "name": "Blind", "cover_type": "blind"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"morning_early": "10:00", "morning_late": "08:00"})
    assert result["type"] == FlowResultType.FORM and result["errors"]


async def test_commands_target_configured_cover_with_own_context(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    await controller.operations.command(58)
    assert calls[-1].service == "set_cover_position"
    assert calls[-1].data == {"entity_id": "cover.blind", "position": 58}
    context = calls[-1].context
    hass.states.async_set("cover.blind", "opening", {"current_position": 75, "supported_features": 15}, context=context)
    await hass.async_block_till_done()
    assert controller.runtime.manual_since is None


async def test_device_feedback_without_context_is_not_a_manual_override(hass, entry):
    config_entry, _ = entry
    controller = config_entry.runtime_data
    await controller.async_control("position", 58)
    # Explicit controls enter manual mode; clear it to test subsequent device feedback alone.
    controller.runtime.manual_since = None
    hass.states.async_set("cover.blind", "closing", {"current_position": 75, "supported_features": 15})
    await hass.async_block_till_done()
    assert controller.runtime.manual_since is None


async def test_external_user_context_records_manual_override(hass, entry):
    config_entry, _ = entry
    controller = config_entry.runtime_data
    hass.states.async_set("cover.blind", "open", {"current_position": 50, "supported_features": 15}, context=Context(user_id="external-user"))
    await hass.async_block_till_done()
    assert controller.runtime.manual_since is not None


async def test_options_reload_preserves_history_and_entity_identity(hass, entry):
    config_entry, _ = entry
    controller = config_entry.runtime_data
    await controller.async_control("position", 58)
    ids = {state.entity_id for state in hass.states.async_all() if state.entity_id.startswith(("sensor.test_blind", "switch.test_blind", "button.test_blind"))}
    hass.config_entries.async_update_entry(config_entry, options={**controller.config, "position_tolerance": 3})
    await hass.async_block_till_done()
    assert config_entry.runtime_data is not controller
    assert config_entry.runtime_data.history
    assert ids <= {state.entity_id for state in hass.states.async_all()}


async def test_unavailable_cover_does_not_receive_command(hass, entry):
    config_entry, calls = entry
    hass.states.async_set("cover.blind", "unavailable")
    await hass.async_block_till_done()
    with pytest.raises(ValueError):
        await config_entry.runtime_data.async_control("position", 58)
    assert calls == []


async def test_clear_override_does_not_break_controller(hass, entry):
    config_entry, _ = entry
    config_entry.runtime_data.runtime.manual_since = dt_util.utcnow().timestamp()
    await config_entry.runtime_data.async_control("clear_override")
    assert config_entry.runtime_data.runtime.manual_since is None
