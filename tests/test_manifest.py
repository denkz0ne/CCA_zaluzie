"""Home Assistant manifest identity and discovery behavior."""

from pathlib import Path

import json


MANIFEST = (
    Path(__file__).parents[1]
    / "custom_components"
    / "cca_zaluzie"
    / "manifest.json"
)


def test_cca_is_registered_as_a_full_service_integration():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "service"
