"""Keep native setup/options descriptions aligned with shared panel metadata."""

import json
from pathlib import Path

from custom_components.cca_zaluzie.config import FIELDS, GROUPS
from custom_components.cca_zaluzie.const import VERSION

COMPONENT = Path(__file__).parents[1] / "custom_components" / "cca_zaluzie"


def test_native_translations_keep_fields_help_and_position_fallback():
    documents = [
        json.loads((COMPONENT / name).read_text(encoding="utf-8"))
        for name in ("strings.json", "translations/sk.json", "translations/en.json")
    ]
    assert documents[0] == documents[1] == documents[2]
    strings = documents[0]
    fallback = strings["config"]["step"]["position_source"]
    assert set(fallback["data"]) == {"position_source", "position_sensor", "drive_time"}
    assert "{reason}" in fallback["description"]
    assert "{reason}" in strings["options"]["step"]["cover"]["description"]
    for group in GROUPS:
        step = strings["options"]["step"][group]
        expected = {k: f for k, f in FIELDS.items() if f.group == group and k != "cover_entity"}
        assert step["data"] == {key: field.label for key, field in expected.items()}
        assert step["data_description"] == {key: field.help for key, field in expected.items()}


def test_release_version_matches_frontend_cache_version():
    assert (
        json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))["version"] == VERSION
    )
