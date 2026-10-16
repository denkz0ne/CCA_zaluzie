"""Serve the actual production panel with isolated browser-test controller fixtures."""

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from astral import Observer
from astral.sun import elevation

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "cca_demo_config", root / "custom_components/cca_zaluzie/config.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
bulk_spec = importlib.util.spec_from_file_location("cca_demo_config.bulk", root / "custom_components/cca_zaluzie/bulk.py")
module.__path__ = []
sys.modules["cca_demo_config.config"] = module
bulk = importlib.util.module_from_spec(bulk_spec)
sys.modules[bulk_spec.name] = bulk
bulk_spec.loader.exec_module(bulk)
now = datetime.now(UTC)
controllers = []
for key, name, entity, position in [
    ("one", "Obývačka · balkón", "cover.one", 58),
    ("two", "Spálňa · okno", "cover.two", 100),
    ("three", "Kuchyňa · okno", "cover.three", 30),
]:
    config = module.validate_config({"cover_entity": entity, "name": name, "morning_early": "06:30" if key == "one" else "07:00"})
    controllers.append(
        {
            "entry_id": key,
            "name": name,
            "cover_entity": entity,
            "position": position,
            "available": True,
            "config": config,
            "config_revision": bulk.config_revision(config),
            "decision": {
                "target": 58,
                "mode": "shading",
                "action": "shade_start",
                "reason": "Slnko je na okne a jas prekročil hranicu.",
                "pending": None,
                "inhibit": None,
                "next_at": None,
                "conditions": {"shade.brightness": True, "shade.azimuth": True},
                "suppressed": ["schedule"],
            },
            "runtime": {
                "shading": True,
                "manual_since": None,
                "reset": None,
                "command": None,
                "fault": None,
            },
            "events": [
                {
                    "id": "example",
                    "at": (now-timedelta(minutes=20)).isoformat(),
                    "type": "command_completed",
                    "details": {"target": 58, "observed": 58},
                }
            ],
            "sensors": {entity: {"state": "open", "attributes": {"current_position": position}}},
            "server_time": now.timestamp(),
            "last_movement": {"direction": "closing", "at": now.isoformat()},
            "next_action": {"action":"close", "label":"Večerné zatvorenie", "target":0, "at":(now+timedelta(minutes=30)).isoformat(), "scheduled_at":(now-timedelta(minutes=5)).isoformat(), "status":"blocked", "blocked_by":"manual", "blocked_until":(now+timedelta(minutes=30)).isoformat(), "detail":"Pôvodný večerný plán čaká na skončenie ochrany manuálneho ovládania. Pred pohybom sa znova overia podmienky."},
            "explanation": {"title":"Prečo je žalúzia v tejto polohe?", "summary":"Manuálne ovládanie zmenilo polohu. Automatika tento zásah rešpektuje do skončenia ochrany.", "details":["Aktívna ochrana manuálneho ovládania.","Návrat k automatickému cieľu je povolený."]},
        }
    )
solar = [
    {"at": (now - timedelta(hours=24) + timedelta(minutes=5 * i)).isoformat(),
     "elevation": elevation(Observer(latitude=48.15, longitude=17.11), now - timedelta(hours=24) + timedelta(minutes=5 * i))}
    for i in range(289)
]

fixture = {"solar": solar,

    "version": json.loads((root / "custom_components/cca_zaluzie/manifest.json").read_text())["version"],
    "order": [c["entry_id"] for c in controllers],
    "order_revision": 0,
    "groups": module.GROUPS,
    "fields": {key: {**value.public(), "bulk_editable": key in bulk.BULK_EDITABLE} for key, value in module.FIELDS.items()},
    "controllers": controllers,
}
(root / "tests/browser/fixture.json").write_text(
    json.dumps(fixture, ensure_ascii=False), encoding="utf-8"
)
ThreadingHTTPServer(
    ("127.0.0.1", 8129), partial(SimpleHTTPRequestHandler, directory=str(root))
).serve_forever()
