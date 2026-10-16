"""Real HA state/store adapter contract for panel presentation and history."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from homeassistant.core import Context
from homeassistant.util import dt as dt_util

from custom_components.cca_zaluzie.controller import CoverController
from custom_components.cca_zaluzie.panel_history import async_recorder_points


@pytest.fixture
def controller(hass):
    return CoverController(
        hass,
        SimpleNamespace(
            entry_id="panel_history",
            title="History",
            data={"cover_entity": "cover.history", "name": "History"},
            options={},
        ),
    )


async def test_measured_state_updates_persist_and_simulation_does_not(hass, controller):
    for position in (30, 40):
        hass.states.async_set(
            "cover.history", "open", {"current_position": position}, context=Context()
        )
        await controller._state_changed(
            SimpleNamespace(
                data={"entity_id": "cover.history", "new_state": hass.states.get("cover.history")}
            )
        )
    assert controller.snapshot()["last_movement"]["direction"] == "opening"
    saved = await controller.store.async_load()
    assert saved["measured_history"]["points"][-1]["position"] == 40
    before = deepcopy(controller.snapshot()["position_history"])
    controller.simulation_enabled = True
    controller.simulation_shadow = {"position": 90}
    assert controller.snapshot()["position_history"] == before
    hass.states.async_remove("cover.history")
    await controller._state_changed(
        SimpleNamespace(data={"entity_id": "cover.history", "new_state": None})
    )
    assert controller.snapshot()["position_history"][-1]["available"] is False


async def test_history_merges_recorder_without_mutating_measured_history(
    hass, controller, monkeypatch
):
    at = dt_util.utcnow().isoformat()

    async def recorder(*args):
        return [{"at": at, "position": 35, "available": True}]

    monkeypatch.setattr(
        "custom_components.cca_zaluzie.panel_history.async_recorder_points", recorder
    )
    before = controller._measured_history.to_dict()
    result = await controller.async_panel_history(24)
    assert result["points"] == [{"at": at, "position": 35, "available": True}]
    assert controller._measured_history.to_dict() == before
    assert set(result) == {"points", "events", "start", "end", "solar", "time_zone"}
    assert result["time_zone"] == hass.config.time_zone
    assert 289 <= len(result["solar"]) <= 292
    assert result["solar"][0]["at"] == result["start"]
    assert result["solar"][-1]["at"] == result["end"]
    assert all(-90 <= point["elevation"] <= 90 for point in result["solar"])
    assert any(point["elevation"] == 0 for point in result["solar"])
    from astral import Observer
    from astral.sun import elevation

    observer = Observer(latitude=hass.config.latitude, longitude=hass.config.longitude)
    assert result["solar"][0]["elevation"] == pytest.approx(
        elevation(observer, dt_util.parse_datetime(result["start"])), abs=0.0001
    )


async def test_missing_recorder_falls_back_to_store(hass, controller):
    controller._measured_history.observe(dt_util.utcnow(), True, 48)
    result = await controller.async_panel_history(6)
    assert result["points"][-1]["position"] == 48
    with pytest.raises(ValueError):
        await controller.async_panel_history(48)


async def test_recorder_query_includes_physical_attribute_changes(hass, controller, monkeypatch):
    from datetime import timedelta

    now = dt_util.utcnow()
    observed = []

    def query(*args, **kwargs):
        observed.append(kwargs)
        return {
            "cover.history": [
                SimpleNamespace(
                    state="open",
                    attributes={"current_position": 38},
                    last_updated=now,
                )
            ]
        }

    async def execute(operation):
        return operation()

    monkeypatch.setattr("homeassistant.components.recorder.history.get_significant_states", query)
    monkeypatch.setattr(
        "homeassistant.helpers.recorder.get_instance",
        lambda _: SimpleNamespace(
            async_add_executor_job=execute,
        ),
    )
    result = await async_recorder_points(hass, controller.config, now - timedelta(hours=6), now)
    assert result[-1]["position"] == 38
    assert observed[0]["significant_changes_only"] is False
    assert observed[0]["no_attributes"] is False
    assert observed[0]["minimal_response"] is False
    assert observed[0]["entity_ids"] == ["cover.history"]


@pytest.mark.parametrize("cover_type", ["awning", "sunshade"])
async def test_controller_direction_respects_reversed_cover_orientation(hass, cover_type):
    controller = CoverController(
        hass,
        SimpleNamespace(
            entry_id="reversed_history",
            title="Reversed history",
            data={"cover_entity": "cover.reversed", "name": "Reversed", "cover_type": cover_type},
            options={},
        ),
    )
    for position in (100, 50):
        hass.states.async_set(
            "cover.reversed", "open", {"current_position": position}, context=Context()
        )
        await controller._state_changed(
            SimpleNamespace(
                data={"entity_id": "cover.reversed", "new_state": hass.states.get("cover.reversed")}
            )
        )
    assert controller.snapshot()["last_movement"]["direction"] == "opening"
