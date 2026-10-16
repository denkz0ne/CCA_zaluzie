"""Read-only panel descriptions and bounded, genuinely measured position history.

This module never evaluates future sensor values or dispatches a motor command.
Schedule bounds come from the same helpers as the production evaluator.
"""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime, timedelta

from .engine import _at, _window
from .model import Decision, Runtime, Snapshot

LABELS = {
    "open": "Ranné otvorenie",
    "close": "Večerné zatvorenie",
    "shade_start": "Začiatok tienenia",
    "shade_end": "Koniec tienenia",
    "ventilate": "Vetranie",
    "ventilate_end": "Návrat po vetraní",
    "manual_end": "Koniec ochrany manuálneho ovládania",
    "idle": "Čaká na ďalší plán",
}
BLOCKS = {
    "manual": "Automatika rešpektuje manuálne ovládanie.",
    "paused": "Automatické riadenie je pozastavené.",
    "disabled": "Automatické riadenie je vypnuté.",
    "instance_disabled": "Riadenie nie je povolené nadradenou podmienkou.",
    "contact_unknown": "Stav okenného kontaktu nie je známy.",
    "contact_pending": "Čaká sa na potvrdenie okenného kontaktu.",
    "contact_lockout": "Zatvorenie čaká na skončenie 30-minútovej ochrany po zatvorení kontaktu.",
    "unavailable": "Žalúzia nie je dostupná.",
    "position_unknown": "Potvrdená poloha žalúzie nie je známa.",
    "condition": "Čaká sa na splnenie podmienok pohybu.",
    "manual_reset_hold": "Ochrana manuálneho ovládania skončila; aktuálna poloha zostáva zachovaná.",
    "explicit_hold": "Aktuálna poloha zostáva zachovaná do ďalšej zmeny riadenia.",
    "startup_hold": "Po obnovení integrácie sa čaká na ďalšiu zmenu riadenia.",
    "behavior_guard": "Pohyb blokuje nastavená ochrana polohy.",
    "once_per_day": "Dnešný pohyb už bol vykonaný.",
    "reset": "Prebieha obnovenie referenčnej polohy.",
    "movement_failed": "Požadovaný pohyb sa nepotvrdil.",
    "force_unknown": "Stav vynúteného ovládania nie je známy.",
    "resident_unknown": "Stav prítomnosti nie je známy.",
    "resident_open": "Otvorenie blokuje nastavenie prítomnosti.",
    "pending_confirmation": "Čaká sa na potvrdenie trvania podmienok.",
    "unowned_target": "Pre tento cieľ nie je povolené automatické riadenie.",
    "schedule_window": "Pohyb čaká na ďalší povolený čas.",
    "movement_merge": "Ranné otvorenie sa zlúči s blízkym potvrdeným tienením.",
}


def _iso(timestamp: float | None, now: datetime) -> str | None:
    return (
        datetime.fromtimestamp(timestamp, now.tzinfo).isoformat() if timestamp is not None else None
    )


def _manual_end(cfg: dict, rt: Runtime, now: datetime) -> float | None:
    if rt.manual_since is None:
        return None
    times = []
    if cfg["manual_timeout"]:
        times.append(rt.manual_since + cfg["manual_timeout"])
    if cfg["manual_reset_daily"]:
        started = datetime.fromtimestamp(rt.manual_since, now.tzinfo)
        due = _at(started, cfg["manual_reset_time"])
        if due.timestamp() <= rt.manual_since:
            due = _at(started + timedelta(days=1), cfg["manual_reset_time"])
        times.append(due.timestamp())
    return min(times) if times else None


def _action(action="idle", **values) -> dict:
    return {
        "action": action,
        "label": LABELS.get(action, "Automatický pohyb"),
        "target": None,
        "at": None,
        "scheduled_at": None,
        "earliest": None,
        "latest": None,
        "status": "waiting_conditions",
        "blocked_by": None,
        "blocked_until": None,
        "detail": "Čaká sa na ďalšiu zmenu podmienok.",
        **values,
    }


def build_presentation(
    cfg: dict, rt: Runtime, snap: Snapshot, decision: Decision, now: datetime
) -> dict:
    """Describe the next intent; times are ISO strings, unknown future times are null."""
    ts = now.timestamp()
    manual = rt.manual_since is not None
    manual_end = _manual_end(cfg, rt, now)
    candidates = []
    if cfg["time_enabled"]:
        for offset in (0, 1):
            day = now + timedelta(days=offset)
            for action, prefix in (("open", "morning"), ("close", "evening")):
                if not cfg[f"{prefix}_enabled"]:
                    continue
                if offset and (
                    cfg["workday_sensor"] or (action == "close" and cfg["workday_tomorrow"])
                ):
                    # A live day-type helper describes today, never a future day.
                    continue
                early, late, known = _window(cfg, snap, day, action)
                if not known:
                    continue
                first, last = _at(day, early).timestamp(), _at(day, late).timestamp()
                deferred = manual and cfg["manual_return"] and rt.base_action == action
                if last < ts and not (offset == 0 and deferred):
                    continue
                if (
                    offset == 0
                    and rt.completed_days.get(action) == day.date().isoformat()
                    and (cfg[f"{action}_once"] or not deferred)
                ):
                    continue
                effective = (
                    max(first, ts, manual_end or ts)
                    if manual and action in cfg["manual_blocks"]
                    else max(first, ts)
                )
                candidates.append((effective, first, last, action))
    # Several schedules may elapse during protection. The last intent owns the
    # target at expiry, matching the evaluator's background schedule updates.
    candidates.sort(key=lambda item: (item[0], -item[1]))
    next_action = _action()
    if candidates:
        _, first, last, action = candidates[0]
        manual_blocks = manual and action in cfg["manual_blocks"]
        earliest = max(first, ts, manual_end or ts) if manual_blocks else max(first, ts)
        sensors = cfg["sun_enabled"]
        conditional = (
            (sensors and first != last and ts < last)
            or bool(cfg["global_conditions"] or cfg.get(f"{action}_conditions"))
            or bool(cfg["resident_sensor"] or cfg["instance_entity"])
            or (cfg["ventilation_enabled"] and bool(cfg["window_open"]))
            or (manual_blocks and manual_end is None)
        )
        next_action = _action(
            action,
            target=cfg[f"{action}_position"],
            at=None if conditional else _iso(earliest, now),
            scheduled_at=_iso(first, now),
            earliest=_iso(earliest, now),
            latest=_iso(max(last, earliest), now),
            status="waiting_conditions"
            if conditional
            else "deferred"
            if manual_blocks
            else "scheduled",
            blocked_by="manual" if manual_blocks else None,
            blocked_until=_iso(manual_end, now) if manual_blocks else None,
            detail=(
                "Pôvodný plán čaká na skončenie ochrany manuálneho ovládania. Potom sa podmienky znova overia."
                if manual_blocks
                else "Pred pohybom sa znova overia aktuálne podmienky."
            ),
        )
        if sensors and conditional:
            next_action["detail"] += " Presný čas závisí od budúceho jasu alebo slnka."
    if decision.mode.startswith("force_"):
        next_action = _action(
            decision.action,
            label="Vynútený pohyb",
            target=decision.target,
            detail="Aktívny vynútený povel má prednosť. Pred pohybom sa overia bezpečnostné podmienky.",
        )
    elif (
        manual
        and not cfg["manual_return"]
        and (next_action["action"] == "idle" or next_action["action"] in cfg["manual_blocks"])
    ):
        next_action = _action(
            "manual_end",
            at=_iso(manual_end, now),
            earliest=_iso(manual_end, now),
            status="scheduled" if manual_end else "waiting_conditions",
            blocked_by="manual",
            blocked_until=_iso(manual_end, now),
            detail="Samotné skončenie ochrany manuálneho ovládania nevyvolá návrat k automatickému cieľu.",
        )
    elif rt.pending in ("shade_start", "shade_end"):
        next_action = _action(
            rt.pending,
            target=decision.target,
            earliest=_iso(rt.pending_due, now),
            detail="Čaká sa na potvrdenie podmienok tienenia; pred pohybom sa overia znova.",
        )
    elif decision.action in ("ventilate", "ventilate_end") or decision.mode == "force":
        next_action = _action(
            decision.action,
            label=LABELS.get(decision.action, "Vynútený pohyb"),
            target=decision.target,
            detail="Pokračovanie závisí od aktuálneho stavu ovládania a bezpečnostných podmienok.",
        )
    block = decision.inhibit
    if block == "contact_lockout" and rt.contact_lockout_until is not None:
        next_action = _action(
            "close",
            label="Zatvorenie po ochrane kontaktu",
            target=cfg["close_position"],
            at=_iso(rt.contact_lockout_until, now),
            earliest=_iso(rt.contact_lockout_until, now),
            status="deferred",
            blocked_by="contact_lockout",
            blocked_until=_iso(rt.contact_lockout_until, now),
            detail=(
                "Zatvorenie je odložené do skončenia ochrany po návrate. "
                "Potom sa znovu overia aktuálne podmienky."
            ),
        )
    if block and block not in (
        "manual",
        "schedule_window",
        "unowned_target",
        "contact_lockout",
        "startup_hold",
        "explicit_hold",
        "manual_reset_hold",
    ):
        next_action.update(
            at=None,
            status="blocked",
            blocked_by=block,
            blocked_until=None,
            detail=BLOCKS.get(block, "Pohyb čaká na splnenie bezpečnostných podmienok."),
        )
    if not cfg["enabled"]:
        next_action.update(
            at=None,
            status="blocked",
            blocked_by="disabled",
            blocked_until=None,
            detail=BLOCKS["disabled"],
        )
    summary = BLOCKS.get(block, "Poloha sa riadi aktuálnym plánom a podmienkami.")
    if manual:
        position = f" na {rt.manual_position:g} %" if rt.manual_position is not None else ""
        started = datetime.fromtimestamp(rt.manual_since, now.tzinfo).strftime("%H:%M")
        summary = f"O {started} bolo zaznamenané manuálne ovládanie{position}."
        summary += (
            f" Automatika ho rešpektuje do {datetime.fromtimestamp(manual_end, now.tzinfo):%H:%M}."
            if manual_end
            else " Automatika rešpektuje ochranu manuálneho ovládania."
        )
        if block and block != "manual":
            summary += " " + BLOCKS.get(block, "Pohyb čaká na splnenie podmienok.")
    return {
        "next_action": next_action,
        "explanation": {
            "title": "Prečo je žalúzia v tejto polohe",
            "summary": summary,
            "details": [next_action["detail"]],
        },
    }


class MeasuredHistory:
    """Finite physical samples only; gaps deliberately break direction inference."""

    def __init__(
        self,
        *,
        limit: int = 10000,
        retention_days: float = 7,
        open_position: float = 100,
        close_position: float = 0,
    ):
        self.limit = max(2, min(int(limit), 20000))
        self.retention_days = max(1, float(retention_days))
        self.points: list[dict] = []
        self.last_movement: dict | None = None
        self._source: str | None = None
        self.orientation = 1 if open_position > close_position else -1

    @classmethod
    def from_dict(cls, data: dict, **kwargs) -> MeasuredHistory:
        result = cls(**kwargs)
        for point in data.get("points", [])[-result.limit :]:
            try:
                at = datetime.fromisoformat(point["at"])
                if at.tzinfo is None:
                    continue
                result.observe(at, point.get("available", False), point.get("position"))
            except (ValueError, TypeError, KeyError):
                continue
        if data.get("orientation", 1) != result.orientation:
            # Old labels were derived under another orientation. Numeric history
            # remains valid, but neither its replay nor its saved label proves
            # what opening meant before the configuration changed.
            result.last_movement = None
            return result
        movement = data.get("last_movement")
        if isinstance(movement, dict) and movement.get("direction") in ("opening", "closing"):
            try:
                if datetime.fromisoformat(movement["at"]).tzinfo is not None:
                    result.last_movement = {
                        "direction": movement["direction"],
                        "at": movement["at"],
                    }
            except (ValueError, TypeError, KeyError):
                pass
        return result

    def to_dict(self) -> dict:
        return deepcopy(
            {
                "points": self.points,
                "last_movement": self.last_movement,
                "orientation": self.orientation,
            }
        )

    def restart(self, now: datetime) -> None:
        # The integration cannot attest to the interval while it was stopped.
        # Break the line immediately after its last known sample, not at restart.
        if self.points and self.points[-1]["available"]:
            at = datetime.fromisoformat(self.points[-1]["at"]) + timedelta(microseconds=1)
            self.observe(min(at, now), False, None)

    def observe(
        self,
        now: datetime,
        available: bool,
        position: float | None,
        *,
        simulated=False,
        source: str | None = None,
    ) -> bool:
        if simulated:
            return False
        if source is not None:
            if self._source is not None and self._source != source:
                self.observe(now - timedelta(microseconds=1), False, None)
            self._source = source
        valid = (
            available
            and isinstance(position, (int, float))
            and not isinstance(position, bool)
            and math.isfinite(position)
            and 0 <= position <= 100
        )
        point = {
            "at": now.isoformat(),
            "position": position if valid else None,
            "available": bool(valid),
        }
        previous = self.points[-1] if self.points else None
        if previous and previous["available"] and valid and previous["position"] != position:
            self.last_movement = {
                "direction": "opening"
                if (position - previous["position"]) * self.orientation > 0
                else "closing",
                "at": point["at"],
            }
        if (
            previous
            and (previous["position"], previous["available"])
            == (point["position"], point["available"])
            and now.timestamp() - datetime.fromisoformat(previous["at"]).timestamp() < 300
        ):
            return False
        self.points.append(point)
        cutoff = now.timestamp() - self.retention_days * 86400
        self.points = [
            p for p in self.points if datetime.fromisoformat(p["at"]).timestamp() >= cutoff
        ][-self.limit :]
        return True

    def read(self, hours: int, now: datetime, events: list[dict]) -> dict:
        if type(hours) is not int or hours not in (6, 24, 168):
            raise ValueError("História podporuje 6 hodín, 24 hodín alebo 7 dní")
        start = now - timedelta(hours=hours)

        def within(item):
            try:
                timestamp = datetime.fromisoformat(item["at"]).timestamp()
                return start.timestamp() <= timestamp <= now.timestamp()
            except (ValueError, TypeError, KeyError):
                return False

        return deepcopy(
            {
                "points": [p for p in self.points if within(p)],
                "events": sorted(
                    [e for e in events if not e.get("simulated") and within(e)],
                    key=lambda e: e["at"],
                ),
                "start": start.isoformat(),
                "end": now.isoformat(),
            }
        )
