"""Retired window-tilt inputs cannot influence a controller after migration."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.cca_zaluzie.config import FIELDS, validate_config
from custom_components.cca_zaluzie.engine import evaluate, mark_manual
from custom_components.cca_zaluzie.model import Reading, Runtime, Snapshot

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=ZoneInfo("Europe/Bratislava"))
RETIRED = {
    "window_tilted": "binary_sensor.retired_tilt",
    "tilted_lockout": "all",
    "tilted_blocks": ["close", "shade_start"],
    "vent_keep_full_tilt": True,
    "vent_lower_from_above": True,
    "vent_after_shade": True,
}


def test_retired_fields_are_accepted_only_for_migration_and_are_not_active_options():
    cfg = validate_config({"cover_entity": "cover.blind", **RETIRED})
    assert not RETIRED.keys() & FIELDS.keys()
    assert not RETIRED.keys() & cfg.keys()


@pytest.mark.parametrize("state", ["on", "off", "unknown", "unavailable"])
def test_retired_contact_never_changes_the_target_or_blocks_the_schedule(state):
    cfg = validate_config({"cover_entity": "cover.blind", "ventilation_enabled": True, **RETIRED})
    snap = Snapshot({"cover.blind": Reading("open", {"current_position": 100}), "binary_sensor.retired_tilt": Reading(state)})
    decision = evaluate(cfg, Runtime(), snap, NOW)
    assert decision.target == 100
    assert decision.inhibit is None
    assert not any("tilt" in key for key in decision.conditions)


def test_old_tilt_runtime_does_not_keep_an_obsolete_ventilation_correction():
    rt = Runtime.from_dict({
        "last_window": "tilted", "keep_full_tilt": True, "generation": 4,
        "correction_mode": "ventilation", "correction_target": 37,
        "correction_base_target": 50, "correction_generation": 4,
        "stable": {"contact.tilted": 123, "contact.tilted.release": 456, "contact.open": 789},
    })
    assert rt.last_window == "closed"
    assert rt.correction_mode is None
    assert rt.correction_target is None
    assert rt.stable == {"contact.open": 789}
    assert "keep_full_tilt" not in rt.to_dict()


def test_one_shot_ventilation_still_accepts_a_small_correction_without_a_tilt_sensor():
    cfg = validate_config({"cover_entity": "cover.blind", "ventilation_enabled": True,
        "morning_enabled": False, "evening_enabled": False, "vent_position": 50})
    rt = Runtime(phase_latches={"vent_start": NOW.date().isoformat()})
    snap = Snapshot({"cover.blind": Reading("open", {"current_position": 50})})
    assert evaluate(cfg, rt, snap, NOW).mode == "ventilation"
    assert mark_manual(cfg, rt, 37, NOW + timedelta(seconds=10), snap)
    assert rt.correction_target == 37



@pytest.mark.parametrize("state", ["on", "off", "unknown", "unavailable"])
def test_prediction_does_not_reintroduce_the_retired_contact(state):
    from custom_components.cca_zaluzie.prediction import compute_prediction

    cfg = validate_config({"cover_entity": "cover.blind", "ventilation_enabled": True, **RETIRED})
    snapshot = Snapshot({"cover.blind": Reading("open", {"current_position": 100}), "binary_sensor.retired_tilt": Reading(state)})
    result = compute_prediction(cfg, Runtime(), snapshot, "Europe/Bratislava", 48.15, 17.11, NOW.date(), 1)
    clean = compute_prediction(cfg, Runtime(), Snapshot({"cover.blind": snapshot.get("cover.blind")}), "Europe/Bratislava", 48.15, 17.11, NOW.date(), 1)
    keys = ("at", "type", "target", "mode", "reason", "status", "confidence", "assumptions")
    assert [{key: event.get(key) for key in keys} for event in result["events"]] == [
        {key: event.get(key) for key in keys} for event in clean["events"]
    ]
