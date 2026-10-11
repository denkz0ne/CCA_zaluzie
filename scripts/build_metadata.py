"""Rebuild checked-in HA field translations from the shared configuration schema."""

import importlib.util
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
component = root / "custom_components" / "cca_zaluzie"
spec = importlib.util.spec_from_file_location("cca_metadata", component / "config.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def step(title, keys):
    return {
        "title": title,
        "description": "{error}",
        "data": {key: module.FIELDS[key].label for key in keys},
        "data_description": {
            key: module.FIELDS[key].help for key in keys if module.FIELDS[key].help
        },
    }


strings = {
    "title": "CCA Žalúzie",
    "config": {
        "step": {
            "user": step("Pridať jednu žalúziu", ["cover_entity", "name", "cover_type"]),
            "schedule": step(
                "Ranný a večerný plán",
                [
                    "time_enabled",
                    "morning_enabled",
                    "evening_enabled",
                    "morning_early",
                    "morning_late",
                    "evening_early",
                    "evening_late",
                ],
            ),
        },
        "error": {"invalid_config": "Skontroluj nastavenia formulára."},
        "abort": {"already_configured": "Táto žalúzia už má automatizáciu."},
    },
    "options": {
        "step": {
            "init": {"title": "Nastavenia žalúzie", "menu_options": module.GROUPS},
            **{
                group: step(
                    title,
                    [
                        key
                        for key, field in module.FIELDS.items()
                        if field.group == group and key != "cover_entity"
                    ],
                )
                for group, title in module.GROUPS.items()
            },
        },
        "error": {"invalid_config": "Skontroluj nastavenia formulára."},
    },
}
for path in [
    component / "strings.json",
    component / "translations" / "sk.json",
    component / "translations" / "en.json",
]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(strings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
