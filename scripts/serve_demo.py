"""Serve the actual production panel with isolated browser-test controller fixtures."""

import importlib.util
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "cca_demo_config", root / "custom_components/cca_zaluzie/config.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
controllers = []
for key, name, entity, position in [
    ("one", "Obývačka · balkón", "cover.one", 58),
    ("two", "Spálňa · okno", "cover.two", 100),
    ("three", "Kuchyňa · okno", "cover.three", 30),
]:
    config = module.validate_config({"cover_entity": entity, "name": name})
    controllers.append(
        {
            "entry_id": key,
            "name": name,
            "cover_entity": entity,
            "position": position,
            "available": True,
            "config": config,
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
                    "at": "2026-10-11T12:42:00+00:00",
                    "type": "command_completed",
                    "details": {"target": 58, "observed": 58},
                }
            ],
            "sensors": {entity: {"state": "open", "attributes": {"current_position": position}}},
            "server_time": 1791723600,
        }
    )
fixture = {
    "version": "2026.10.0",
    "groups": module.GROUPS,
    "fields": {key: value.public() for key, value in module.FIELDS.items()},
    "controllers": controllers,
}
(root / "tests/browser/fixture.json").write_text(
    json.dumps(fixture, ensure_ascii=False), encoding="utf-8"
)
ThreadingHTTPServer(
    ("127.0.0.1", 8129), partial(SimpleHTTPRequestHandler, directory=str(root))
).serve_forever()
