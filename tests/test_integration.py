"""Real HA config entries, service calls and controller lifecycle."""

import asyncio
from copy import deepcopy

import pytest

pytest.importorskip("homeassistant")

from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Context
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cca_zaluzie import async_migrate_entry
from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.const import DOMAIN
from custom_components.cca_zaluzie.operations import OperationError


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
    hass.states.async_set(
        "cover.blind", "open", {"current_position": 100, "supported_features": 15}
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test blind",
        unique_id="cover.blind",
        data=validate_config(
            {
                "cover_entity": "cover.blind",
                "name": "Test blind",
                "morning_enabled": False,
                "evening_enabled": False,
            }
        ),
    )
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"cover_entity": "cover.blind", "name": "Blind", "cover_type": "blind"}
    )
    assert result["step_id"] == "schedule"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "time_enabled": True,
            "morning_enabled": True,
            "evening_enabled": True,
            "morning_early": "06:30",
            "morning_late": "08:00",
            "evening_early": "18:00",
            "evening_late": "21:30",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["position_source_auto"] is True
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"cover_entity": "cover.blind", "name": "Other", "cover_type": "blind"},
    )
    assert duplicate["type"] == FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_invalid_schedule_stays_in_flow(hass):
    hass.states.async_set("cover.blind", "open")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"cover_entity": "cover.blind", "name": "Blind", "cover_type": "blind"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"position_source": "current_position"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"morning_early": "10:00", "morning_late": "08:00"}
    )
    assert result["type"] == FlowResultType.FORM and result["errors"]


async def test_setup_asks_for_manual_source_when_feedback_missing(hass):
    hass.states.async_set("cover.blind", "open")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"cover_entity": "cover.blind", "name": "Blind", "cover_type": "blind"}
    )
    assert result["step_id"] == "position_source"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"position_source": "drive_time", "drive_time": 72}
    )
    assert result["step_id"] == "schedule"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "time_enabled": True,
            "morning_enabled": True,
            "evening_enabled": True,
            "morning_early": "06:30",
            "morning_late": "08:00",
            "evening_early": "18:00",
            "evening_late": "21:30",
        },
    )
    assert result["data"]["position_source_auto"] is False
    assert result["data"]["position_source"] == "drive_time"


async def test_commands_target_configured_cover_with_own_context(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    await controller.operations.command(58)
    assert calls[-1].service == "set_cover_position"
    assert calls[-1].data == {"entity_id": "cover.blind", "position": 58}
    context = calls[-1].context
    hass.states.async_set(
        "cover.blind",
        "opening",
        {"current_position": 75, "supported_features": 15},
        context=context,
    )
    await hass.async_block_till_done()
    assert controller.runtime.manual_since is None


async def test_device_feedback_without_context_is_not_a_manual_override(hass, entry):
    config_entry, _ = entry
    controller = config_entry.runtime_data
    await controller.async_control("position", 58)
    # Explicit controls enter manual mode; clear it to test subsequent device feedback alone.
    controller.runtime.manual_since = None
    hass.states.async_set(
        "cover.blind", "closing", {"current_position": 75, "supported_features": 15}
    )
    await hass.async_block_till_done()
    assert controller.runtime.manual_since is None


async def test_external_user_context_records_manual_override(hass, entry):
    config_entry, _ = entry
    controller = config_entry.runtime_data
    hass.states.async_set(
        "cover.blind",
        "open",
        {"current_position": 50, "supported_features": 15},
        context=Context(user_id="external-user"),
    )
    await hass.async_block_till_done()
    assert controller.runtime.manual_since is not None


async def test_options_reload_preserves_history_and_entity_identity(hass, entry):
    config_entry, _ = entry
    controller = config_entry.runtime_data
    await controller.async_control("position", 58)
    ids = {
        state.entity_id
        for state in hass.states.async_all()
        if state.entity_id.startswith(
            ("sensor.test_blind", "switch.test_blind", "button.test_blind")
        )
    }
    hass.config_entries.async_update_entry(
        config_entry, options={**controller.config, "position_tolerance": 3}
    )
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


async def test_selected_position_sensor_completes_a_command(hass, entry):
    config_entry, _ = entry
    hass.states.async_set("sensor.feedback", "100")
    options = {
        **config_entry.runtime_data.config,
        "position_source": "sensor",
        "position_sensor": "sensor.feedback",
        "position_source_auto": False,
    }
    hass.config_entries.async_update_entry(config_entry, options=options)
    await hass.async_block_till_done()
    controller = config_entry.runtime_data
    await controller.operations.command(58)
    hass.states.async_set("sensor.feedback", "58")
    await hass.async_block_till_done()
    assert controller.runtime.command["status"] == "completed"
    assert controller.runtime.manual_since is None


async def test_unknown_selected_sensor_is_not_replaced_by_cover_position(hass, entry):
    config_entry, _ = entry
    hass.states.async_set("sensor.feedback", "unavailable")
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **config_entry.runtime_data.config,
            "position_source": "sensor",
            "position_sensor": "sensor.feedback",
            "position_source_auto": False,
        },
    )
    await hass.async_block_till_done()
    assert config_entry.runtime_data.observe() == (True, None)
    assert config_entry.runtime_data.decision.inhibit == "position_unknown"


async def test_fast_service_feedback_does_not_regress_completed_to_moving(hass, entry):
    import asyncio

    config_entry, _ = entry

    async def move(call):
        hass.states.async_set(
            "cover.blind",
            "open",
            {"current_position": call.data["position"], "supported_features": 15},
            context=call.context,
        )
        await asyncio.sleep(0)

    hass.services.async_register("cover", "set_cover_position", move)
    await config_entry.runtime_data.operations.command(58)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.runtime.command["status"] == "completed"


async def test_native_action_alias_and_template_are_normalized(hass, entry):
    config_entry, _ = entry
    values = []

    async def capture(call):
        values.append(call.data["value"])

    hass.services.async_register("test", "capture", capture)
    options = {
        **config_entry.runtime_data.config,
        "open_after": [{"action": "test.capture", "data": {"value": "{{ target }}"}}],
    }
    hass.config_entries.async_update_entry(config_entry, options=options)
    await hass.async_block_till_done()
    controller = config_entry.runtime_data
    controller.decision.target = 100
    await controller._run_script("open_after")
    assert values == [100]


async def test_generic_ha_service_cannot_bypass_panel_admin_permissions(
    hass, entry, hass_ws_client, hass_read_only_access_token
):
    config_entry, calls = entry
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json(
        {
            "id": 1,
            "type": "call_service",
            "domain": DOMAIN,
            "service": "control",
            "service_data": {"entry_id": config_entry.entry_id, "action": "close"},
        }
    )
    result = await client.receive_json()
    assert result["success"] is False
    assert calls == []


async def test_stop_cancels_pending_automation_even_when_manual_detection_is_disabled(hass, entry):
    import asyncio

    config_entry, calls = entry
    controller = config_entry.runtime_data
    controller.config.update(
        drive_delay=3600, manual_enabled=False, time_enabled=False, evening_enabled=True
    )
    today = dt_util.now().date().isoformat()
    controller.runtime.logical_days = {"open": today, "close": today}
    controller.runtime.schedule_latched = {"open": True, "close": True}
    controller.runtime.base_target = 0
    controller.runtime.base_action = "close"
    controller.runtime.base_owned = True
    controller.runtime.hold_signature = None
    await controller.async_evaluate()
    await asyncio.sleep(0)
    await controller.async_control("stop")
    await hass.async_block_till_done()
    assert [call.service for call in calls] == ["stop_cover"]
    assert controller._dispatch_task.done()


async def test_options_reload_cancels_reset_and_attempts_stop(hass, entry):
    import asyncio

    config_entry, calls = entry
    controller = config_entry.runtime_data
    gate = asyncio.Event()

    async def wait(_seconds):
        await gate.wait()

    controller.sleep = wait
    await controller.async_control("reset")
    await asyncio.sleep(0)
    hass.config_entries.async_update_entry(
        config_entry, options={**controller.config, "position_tolerance": 3}
    )
    await hass.async_block_till_done()
    assert calls[-1].service == "stop_cover"
    assert config_entry.runtime_data.runtime.reset["status"] == "cancelled"


@pytest.mark.parametrize(
    "group",
    [
        "cover",
        "schedule",
        "light",
        "shading",
        "windows",
        "manual",
        "resident",
        "advanced",
        "records",
    ],
)
async def test_every_native_options_section_opens(hass, entry, group):
    config_entry, _ = entry
    menu = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": group}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group


async def test_auto_position_source_is_hidden_until_feedback_is_unresolved(hass, entry):
    config_entry, _ = entry
    menu = await hass.config_entries.options.async_init(config_entry.entry_id)
    form = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cover"}
    )
    keys = {marker.schema for marker in form["data_schema"].schema}
    assert "position_source" not in keys

    hass.states.async_set("cover.blind", "open")
    menu = await hass.config_entries.options.async_init(config_entry.entry_id)
    form = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cover"}
    )
    keys = {marker.schema for marker in form["data_schema"].schema}
    assert "position_source" in keys


async def test_automatic_source_falls_back_and_conflicts_block_commands(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    hass.states.async_set("cover.blind", "open", {"current_position": "unknown", "position": 71})
    await hass.async_block_till_done()
    assert controller.position_source == "position"
    assert controller.observe() == (True, 71)

    hass.states.async_set("cover.blind", "open", {"current_position": 100, "position": 50})
    await hass.async_block_till_done()
    assert controller.position_source is None
    assert controller.snapshot()["position_source"]["reason"] == "ambiguous_position_feedback"
    with pytest.raises(OperationError, match="Automaticky sa nenašla"):
        await controller.operations.command(58, force=True)
    assert calls == []


async def test_panel_serves_the_production_module_and_stylesheet(hass, entry, hass_client):
    client = await hass_client()
    response = await client.get("/cca_zaluzie/frontend/cca-zaluzie-panel.js")
    assert response.status == 200
    assert "cca-zaluzie-panel" in await response.text()
    response = await client.get("/cca_zaluzie/frontend/panel.css")
    assert response.status == 200


async def test_external_cover_service_interrupts_reset(hass, entry):
    import asyncio

    config_entry, calls = entry
    controller = config_entry.runtime_data
    gate = asyncio.Event()

    async def wait(_seconds):
        await gate.wait()

    controller.sleep = wait
    await controller.async_control("reset")
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.blind"},
        blocking=True,
        context=Context(user_id="external-user"),
    )
    await hass.async_block_till_done()
    assert controller.runtime.reset["status"] in ("interrupted", "failed")
    assert not any(event["type"] == "reset_completed" for event in controller.history)
    assert calls[-1].service == "stop_cover"


async def test_panel_rejects_blank_numeric_config_without_changing_the_entry(
    hass, entry, hass_ws_client
):
    config_entry, _ = entry
    client = await hass_ws_client(hass)
    config = {**config_entry.runtime_data.config, "open_position": None}
    await client.send_json(
        {
            "id": 1,
            "type": "cca_zaluzie/configure",
            "entry_id": config_entry.entry_id,
            "config": config,
        }
    )
    result = await client.receive_json()
    assert result["success"] is False and result["error"]["code"] == "invalid_config"
    assert config_entry.runtime_data.config["open_position"] == 100


async def test_simulation_records_motor_command_without_calling_cover_service(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data

    await controller.async_set_simulation(True)
    await controller.async_control("close")
    await hass.async_block_till_done()

    assert calls == []
    assert controller.snapshot()["simulation"]["enabled"] is True
    assert any(event["type"] == "would_dispatch" for event in controller.simulation_history)


async def test_simulated_motion_advances_only_the_virtual_position(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data

    physical_position = hass.states.get("cover.blind").attributes["current_position"]
    await controller.async_set_simulation(True)
    controller.simulation_shadow["position"] = 100
    await controller.service("close_cover", {})
    assert controller.observe_simulation()[1] == 100
    with pytest.raises(OperationError, match="simulovaný pohyb"):
        await controller.async_set_simulation(False)
    assert calls == []

    await controller.sleep(controller.config["drive_time"] / 2)
    position = controller.observe_simulation()[1]

    assert 45 <= position <= 55
    assert hass.states.get("cover.blind").attributes["current_position"] == physical_position
    assert calls == []


async def test_simulated_stop_and_cancelled_reset_never_call_motor(hass, entry, monkeypatch):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    await controller.async_set_simulation(True)
    await controller.async_control("stop")

    entered_wait = asyncio.Event()
    release_wait = asyncio.Event()
    original_sleep = controller.sleep

    async def blocked_sleep(seconds):
        entered_wait.set()
        await release_wait.wait()
        await original_sleep(seconds)

    monkeypatch.setattr(controller, "sleep", blocked_sleep)
    await controller.async_control("reset")
    await entered_wait.wait()
    await controller.operations.cancel_reset()

    assert calls == []
    assert controller.runtime.reset["status"] == "cancelled"
    assert any(event["type"] == "would_dispatch" for event in controller.simulation_history)


async def test_simulation_suppresses_native_actions(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data

    class SideEffect:
        async def async_run(self, *args, **kwargs):
            calls.append("native action ran")

    controller._scripts["open_before"] = SideEffect()
    await controller.async_set_simulation(True)
    await controller._run_script("open_before")

    assert calls == []
    assert any(
        event["type"] == "action_suppressed" for event in controller.simulation_history
    )


async def test_simulation_isolated_to_one_cover(hass, entry):
    first_entry, calls = entry
    hass.states.async_set(
        "cover.other", "open", {"current_position": 100, "supported_features": 15}
    )
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other blind",
        unique_id="cover.other",
        data=validate_config(
            {
                "cover_entity": "cover.other",
                "name": "Other blind",
                "morning_enabled": False,
                "evening_enabled": False,
            }
        ),
    )
    second_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    await first_entry.runtime_data.async_set_simulation(True)
    assert second_entry.runtime_data.snapshot()["simulation"]["enabled"] is False
    await second_entry.runtime_data.async_control("close")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["entity_id"] == "cover.other"
    await hass.config_entries.async_unload(second_entry.entry_id)


async def test_simulation_mode_is_saved_for_restart(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data

    await controller.async_set_simulation(True)
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.runtime_data.snapshot()["simulation"]["enabled"] is True
    assert calls == []


async def test_simulated_reset_never_calls_motor_and_is_not_hardware_success(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data

    await controller.async_set_simulation(True)
    await controller.async_control("reset")
    await controller.operations.reset_task
    await hass.async_block_till_done()

    assert calls == []
    assert controller.runtime.reset["status"] == "simulated_completed"
    assert any(
        event["type"] == "simulated_reset_completed" for event in controller.simulation_history
    )


async def test_simulation_keeps_unavailable_cover_blocked(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    await controller.async_set_simulation(True)
    hass.states.async_set("cover.blind", "unavailable")

    with pytest.raises(OperationError, match="nie je dostupná"):
        await controller.async_control("close")

    assert calls == []


async def test_disabling_simulation_does_not_dispatch_virtual_work(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    controller.decision.target = 0

    await controller.async_set_simulation(True)
    await controller.async_control("close")
    with pytest.raises(OperationError, match="simulovaný pohyb"):
        await controller.async_set_simulation(False)
    await controller.async_control("stop")
    await controller.async_set_simulation(False)
    await hass.async_block_till_done()

    assert calls == []
    assert controller.snapshot()["simulation"]["enabled"] is False


async def test_prediction_has_no_ha_side_effects(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    before_runtime = deepcopy(controller.runtime.to_dict())
    before_history = deepcopy(controller.history)
    service_calls = []
    remove_listener = hass.bus.async_listen(
        EVENT_CALL_SERVICE,
        lambda event: service_calls.append(event.data),
    )
    result = await controller.async_predict("2026-10-20", 1)
    await hass.async_block_till_done()
    remove_listener()

    assert result["start_date"] == "2026-10-20"
    assert service_calls == []
    assert calls == []
    assert controller.runtime.to_dict() == before_runtime
    assert controller.history == before_history


async def test_live_prediction_keeps_runtime_and_never_dispatches(hass, entry):
    config_entry, calls = entry
    controller = config_entry.runtime_data
    before_runtime = deepcopy(controller.runtime.to_dict())
    before_history = deepcopy(controller.history)
    service_calls = []
    remove_listener = hass.bus.async_listen(
        EVENT_CALL_SERVICE,
        lambda event: service_calls.append(event.data),
    )

    result = await controller.async_predict(None, 2, from_now=True)
    await hass.async_block_till_done()
    remove_listener()

    assert result["start_date"] == dt_util.now().date().isoformat()
    assert result["current"]["inputs"]
    assert service_calls == []
    assert calls == []
    assert controller.runtime.to_dict() == before_runtime
    assert controller.history == before_history


async def test_config_entry_migration_retires_schedule_light_and_calendar_only(hass):
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test blind",
        unique_id="cover.blind",
        version=1,
        minor_version=1,
        data={"cover_entity": "cover.blind", "name": "Test blind", "morning_late": "08:15"},
        options={
            "calendar_enabled": True,
            "calendar_entity": "calendar.old",
            "lux_enabled": True,
            "lux_sensor": "sensor.old_lux",
            "shade_lux_sensor": "sensor.shade_lux",
        },
    )
    config_entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, config_entry)

    assert config_entry.minor_version == 2
    assert config_entry.options == {}
    assert config_entry.data["morning_late"] == "08:15"
    assert config_entry.data["shade_lux_sensor"] == "sensor.shade_lux"
    assert "calendar_entity" not in config_entry.data
    assert "calendar_enabled" not in config_entry.data
    assert "lux_enabled" not in config_entry.data
    assert config_entry.data["cover_entity"] == "cover.blind"
