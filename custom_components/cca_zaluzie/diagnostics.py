"""Diagnostics omit custom action/condition payloads and credential-like keys."""

from .config import FIELDS
from .const import VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    snapshot = entry.runtime_data.snapshot()
    for key, spec in FIELDS.items():
        if spec.kind in ("action", "condition"):
            snapshot["config"][key] = "<redacted custom automation>"

    def redact(value):
        if isinstance(value, dict):
            return {
                k: "<redacted>"
                if any(
                    word in k.lower()
                    for word in ("password", "token", "secret", "authorization", "api_key")
                )
                else redact(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value

    return {"version": VERSION, "controller": redact(snapshot)}
