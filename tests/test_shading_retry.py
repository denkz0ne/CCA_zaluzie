"""Native condition failures must remain bounded pending transitions."""

from datetime import timedelta

from test_engine import NOW, shade_config, shaded_world

from custom_components.cca_zaluzie.engine import evaluate
from custom_components.cca_zaluzie.model import Runtime


def test_native_start_condition_retries_without_claiming_active_shading():
    cfg = shade_config(shade_start_delay=10, shade_start_max=25)
    rt = Runtime()
    snap = shaded_world()
    snap.gates = {"shade_start": False}
    now = NOW.replace(hour=12)
    evaluate(cfg, rt, snap, now)
    decision = evaluate(cfg, rt, snap, now + timedelta(seconds=10))
    assert rt.shading is False
    assert decision.pending == "shade_start"
    assert decision.next_at == (now + timedelta(seconds=20)).timestamp()
    evaluate(cfg, rt, snap, now + timedelta(seconds=30))
    assert rt.shading is False and rt.pending is None
    assert "shade_start" in rt.expired


def test_condition_recovery_waits_for_the_pending_retry_deadline():
    cfg = shade_config(shade_start_delay=10, shade_start_max=60)
    rt = Runtime()
    snap = shaded_world()
    snap.gates = {"shade_start": False}
    now = NOW.replace(hour=12)
    evaluate(cfg, rt, snap, now)
    evaluate(cfg, rt, snap, now + timedelta(seconds=10))
    snap.gates["shade_start"] = True
    decision = evaluate(cfg, rt, snap, now + timedelta(seconds=11))
    assert rt.shading is False and decision.inhibit == "pending_confirmation"
    assert evaluate(cfg, rt, snap, now + timedelta(seconds=20)).target == 58
    assert rt.shading is True
