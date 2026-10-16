"""Native setup and grouped options without YAML helpers."""

from __future__ import annotations

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .config import FIELDS, GROUPS, ConfigError, validate_config
from .const import DOMAIN
from .position import detect_position_source


def _detection(hass, config):
    state = hass.states.get(config["cover_entity"])
    attributes = state.attributes if state and state.state not in ("unknown", "unavailable") else {}
    return detect_position_source(attributes, config["position_tolerance"])


def field_selector(spec):
    if spec.kind == "number":
        return selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=spec.minimum,
                max=spec.maximum,
                mode=selector.NumberSelectorMode.BOX,
                **({"unit_of_measurement": spec.unit} if spec.unit else {}),
            )
        )
    if spec.kind == "bool":
        return selector.BooleanSelector()
    if spec.kind == "time":
        return selector.TimeSelector()
    if spec.kind == "entity":
        domain = (
            "cover"
            if spec.key == "cover_entity"
            else "calendar"
            if spec.key == "calendar_entity"
            else None
        )
        return selector.EntitySelector(
            selector.EntitySelectorConfig(**({"domain": domain} if domain else {}))
        )
    if spec.kind in ("select", "multi"):
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(spec.options),
                multiple=spec.kind == "multi",
                mode=selector.SelectSelectorMode.LIST
                if spec.kind == "multi"
                else selector.SelectSelectorMode.DROPDOWN,
            )
        )
    if spec.kind in ("action", "condition"):
        return selector.selector({spec.kind: {}})
    return selector.TextSelector()


def build_schema(config: dict, keys: list[str]) -> vol.Schema:
    schema = {}
    for key in keys:
        spec = FIELDS[key]
        value = config.get(key, spec.default)
        marker = (
            vol.Optional(key, description={"suggested_value": value})
            if spec.kind == "entity" and key != "cover_entity"
            else vol.Required(key, default=value)
        )
        schema[marker] = field_selector(spec)
    return vol.Schema(schema)


async def async_validate_native(hass, config: dict) -> None:
    """Use HA's parser for nested conditions/actions before committing settings."""
    from homeassistant.helpers import condition
    from homeassistant.helpers.script import async_validate_actions_config

    for key, spec in FIELDS.items():
        if not config[key]:
            continue
        if spec.kind == "condition":
            await condition.async_validate_conditions_config(hass, config[key])
        elif spec.kind == "action":
            await async_validate_actions_config(hass, cv.SCRIPT_SCHEMA(config[key]))


class CCAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 3

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        errors, details = {}, ""
        if user_input is not None:
            try:
                self._data = validate_config(user_input)
                if self.hass.states.get(self._data["cover_entity"]) is None:
                    raise ConfigError("cover_entity", "entita nie je v Home Assistante")
                await self.async_set_unique_id(self._data["cover_entity"])
                self._abort_if_unique_id_configured()
                detected = _detection(self.hass, self._data)
                if detected.automatic:
                    self._data["position_source"] = detected.source
                    self._data["position_source_auto"] = True
                    return await self.async_step_schedule()
                self._data["position_source_auto"] = False
                return await self.async_step_position_source()
            except ConfigError as error:
                errors["base"], details = "invalid_config", str(error)
        return self.async_show_form(
            step_id="user",
            data_schema=build_schema(user_input or {}, ["cover_entity", "name", "cover_type"]),
            errors=errors,
            description_placeholders={"error": details},
        )

    async def async_step_position_source(self, user_input=None):
        errors, details = {}, ""
        if user_input is not None:
            try:
                self._data = validate_config({**self._data, **user_input, "position_source_auto": False})
                return await self.async_step_schedule()
            except ConfigError as error:
                errors["base"], details = "invalid_config", str(error)
        keys = ["position_source", "position_sensor", "drive_time"]
        detection = _detection(self.hass, self._data)
        reason = (
            "Home Assistant hlási dve rozdielne polohy. Vyber zdroj ručne."
            if detection.reason == "ambiguous_position_feedback"
            else "Spätná väzba polohy nie je dostupná. Vyber zdroj ručne."
        )
        return self.async_show_form(
            step_id="position_source",
            data_schema=build_schema({**self._data, **(user_input or {})}, keys),
            errors=errors,
            description_placeholders={"error": details, "reason": reason},
        )

    async def async_step_schedule(self, user_input=None):
        keys = [
            "time_enabled",
            "morning_enabled",
            "evening_enabled",
            "morning_early",
            "morning_late",
            "evening_early",
            "evening_late",
        ]
        errors, details = {}, ""
        if user_input is not None:
            try:
                config = validate_config({**self._data, **user_input})
                return self.async_create_entry(title=config["name"], data=config)
            except ConfigError as error:
                errors["base"], details = "invalid_config", str(error)
        return self.async_show_form(
            step_id="schedule",
            data_schema=build_schema({**self._data, **(user_input or {})}, keys),
            errors=errors,
            description_placeholders={"error": details},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CCAOptionsFlow()


class CCAOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=list(GROUPS))

    async def _group(self, group: str, user_input=None):
        config = validate_config({**self.config_entry.data, **self.config_entry.options})
        keys = [k for k, spec in FIELDS.items() if spec.group == group and k != "cover_entity"]
        detected = _detection(self.hass, config)
        if group == "cover" and config.get("position_source_auto") and detected.automatic:
            keys.remove("position_source")
        errors, details = {}, ""
        if user_input is not None:
            try:
                patch = {
                    k: user_input.get(k, "")
                    if FIELDS[k].kind == "entity"
                    else user_input.get(k, config[k])
                    for k in keys
                }
                candidate = validate_config(
                    {**config, **patch},
                    cover_entity=self.config_entry.data["cover_entity"],
                )
                if "position_source" in user_input:
                    candidate["position_source_auto"] = False
                await async_validate_native(self.hass, candidate)
                return self.async_create_entry(title="", data=candidate)
            except (ConfigError, vol.Invalid, ValueError) as error:
                errors["base"], details = "invalid_config", str(error)
        return self.async_show_form(
            step_id=group,
            data_schema=build_schema({**config, **(user_input or {})}, keys),
            errors=errors,
            description_placeholders={
                "error": details,
                "reason": (
                    "Home Assistant hlási dve rozdielne polohy. Vyber zdroj ručne."
                    if group == "cover"
                    and config.get("position_source_auto")
                    and detected.reason == "ambiguous_position_feedback"
                    else "Spätná väzba polohy nie je dostupná. Vyber zdroj ručne."
                    if group == "cover" and config.get("position_source_auto") and not detected.automatic
                    else ""
                ),
            },
        )


def _step(group):
    async def handler(self, user_input=None):
        return await self._group(group, user_input)

    return handler


for _group_name in GROUPS:
    setattr(CCAOptionsFlow, f"async_step_{_group_name}", _step(_group_name))
