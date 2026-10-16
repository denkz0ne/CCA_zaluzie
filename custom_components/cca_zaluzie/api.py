"""Admin-only WebSocket panel API using the same live per-cover controller."""

from __future__ import annotations

import asyncio
from pathlib import Path

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.core import Context, callback

from .bulk import BULK_EDITABLE, async_save_configs, config_revision, prepare_bulk
from .config import FIELDS, GROUPS, validate_config
from .config_flow import async_validate_native
from .const import DOMAIN, EVENT_UPDATED, PANEL_PATH, VERSION
from .panel_state import PanelState


def _controllers(hass):
    return hass.data[DOMAIN]["controllers"]


def _config_lock(hass):
    return hass.data[DOMAIN].setdefault("config_lock", asyncio.Lock())


def _current_config(hass, entry_id):
    controller = _controllers(hass).get(entry_id)
    if controller is None:
        return None
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        return None
    return validate_config({**entry.data, **entry.options})


def _snapshot(hass, controller):
    result = controller.snapshot()
    config = _current_config(hass, controller.entry.entry_id)
    if config is not None:
        result["config"] = config
        result["config_revision"] = config_revision(config)
    return result


def _order(hass):
    state = hass.data[DOMAIN].get("panel_state")
    if state:
        return state.snapshot(_controllers(hass))
    return {"order": list(_controllers(hass)), "order_revision": 0}


def _save(hass, entry_id, config):
    entry = hass.config_entries.async_get_entry(entry_id)
    hass.config_entries.async_update_entry(entry, title=config["name"], options=config)


def _get(hass, connection, msg):
    controller = _controllers(hass).get(msg["entry_id"])
    if controller is None:
        connection.send_error(msg["id"], "not_found", "Žalúzia už nie je načítaná")
    return controller


@websocket_api.websocket_command({vol.Required("type"): "cca_zaluzie/list"})
@websocket_api.require_admin
@callback
def ws_list(hass, connection, msg):
    connection.send_result(
        msg["id"],
        {
            "version": VERSION,
            "groups": GROUPS,
            "fields": {
                key: {**spec.public(), "bulk_editable": key in BULK_EDITABLE}
                for key, spec in FIELDS.items()
            },
            **_order(hass),
            "controllers": [
                _snapshot(hass, controller) for controller in _controllers(hass).values()
            ],
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "cca_zaluzie/get", vol.Required("entry_id"): str}
)
@websocket_api.require_admin
@callback
def ws_get(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        connection.send_result(msg["id"], _snapshot(hass, controller))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "cca_zaluzie/control",
        vol.Required("entry_id"): str,
        vol.Required("action"): vol.In(
            [
                "open",
                "close",
                "stop",
                "shade",
                "ventilate",
                "position",
                "enable",
                "disable",
                "clear_override",
                "reconcile",
                "reset",
                "cancel_reset",
                "simulation_on",
                "simulation_off",
            ]
        ),
        vol.Optional("position"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_control(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        try:
            async with _config_lock(hass):
                # Resolve after waiting: options reload can replace the controller.
                controller = _get(hass, connection, msg)
                if controller is None:
                    return
                await controller.async_control(
                    msg["action"], msg.get("position"), context=Context(user_id=connection.user.id)
                )
            connection.send_result(msg["id"], _snapshot(hass, controller))
        except Exception as error:
            connection.send_error(msg["id"], "operation_failed", str(error))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "cca_zaluzie/configure",
        vol.Required("entry_id"): str,
        vol.Required("config"): dict,
        vol.Optional("expected_revision"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_configure(hass, connection, msg):
    async with _config_lock(hass):
        if _get(hass, connection, msg):
            try:
                entry_id = msg["entry_id"]
                original = _current_config(hass, entry_id)
                if original is None:
                    raise ValueError("Žalúzia už neexistuje")
                if "expected_revision" in msg and msg["expected_revision"] != config_revision(
                    original
                ):
                    raise ValueError("Nastavenia sa medzitým zmenili; obnov zobrazenie")
                config = validate_config(msg["config"], cover_entity=original["cover_entity"])
                await async_save_configs(
                    {entry_id: config},
                    {entry_id: original},
                    lambda key: _current_config(hass, key),
                    lambda cfg: async_validate_native(hass, cfg),
                    lambda key, cfg: _save(hass, key, cfg),
                )
                connection.send_result(
                    msg["id"],
                    {"saved": True, "config": config, "config_revision": config_revision(config)},
                )
            except Exception as error:
                connection.send_error(msg["id"], "invalid_config", str(error))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "cca_zaluzie/configure_bulk",
        vol.Required("entry_ids"): [str],
        vol.Required("patch"): dict,
        vol.Required("revisions"): {str: str},
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_configure_bulk(hass, connection, msg):
    async with _config_lock(hass):
        try:
            originals = {key: _current_config(hass, key) for key in msg["entry_ids"]}
            configs = prepare_bulk(originals, msg["entry_ids"], msg["patch"], msg["revisions"])
            await async_save_configs(
                configs,
                originals,
                lambda key: _current_config(hass, key),
                lambda cfg: async_validate_native(hass, cfg),
                lambda key, cfg: _save(hass, key, cfg),
            )
            connection.send_result(
                msg["id"],
                {
                    "saved": True,
                    "configs": configs,
                    "config_revisions": {key: config_revision(cfg) for key, cfg in configs.items()},
                },
            )
        except Exception as error:
            connection.send_error(msg["id"], "invalid_config", str(error))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "cca_zaluzie/reorder",
        vol.Required("entry_ids"): [str],
        vol.Required("revision"): vol.All(int, vol.Range(min=0)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_reorder(hass, connection, msg):
    try:
        result = await hass.data[DOMAIN]["panel_state"].async_reorder(
            msg["entry_ids"], msg["revision"], lambda: list(_controllers(hass))
        )
        hass.bus.async_fire(EVENT_UPDATED, result)
        connection.send_result(msg["id"], result)
    except Exception as error:
        connection.send_error(msg["id"], "invalid_order", str(error))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "cca_zaluzie/history",
        vol.Required("entry_id"): str,
        vol.Optional("hours", default=24): vol.In([6, 24, 168]),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_history(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        try:
            result = await controller.async_panel_history(msg["hours"])
            connection.send_result(msg["id"], result)
        except Exception as error:
            connection.send_error(msg["id"], "history_failed", str(error))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "cca_zaluzie/predict",
        vol.Required("entry_id"): str,
        vol.Optional("start_date"): str,
        vol.Optional("days", default=2): vol.All(vol.Coerce(int), vol.Range(min=1, max=7)),
        vol.Optional("from_now", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_predict(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        try:
            result = await controller.async_predict(
                msg.get("start_date"), msg["days"], from_now=msg["from_now"]
            )
            connection.send_result(msg["id"], result)
        except Exception as error:
            connection.send_error(msg["id"], "prediction_failed", str(error))


@websocket_api.websocket_command({vol.Required("type"): "cca_zaluzie/subscribe"})
@websocket_api.require_admin
@callback
def ws_subscribe(hass, connection, msg):
    @callback
    def updated(event):
        if "entry_id" not in event.data:
            connection.send_event(msg["id"], _order(hass))
            return
        controller = _controllers(hass).get(event.data["entry_id"])
        connection.send_event(
            msg["id"],
            {
                "entry_id": event.data["entry_id"],
                "controller": _snapshot(hass, controller) if controller else None,
                "removed": event.data.get("removed", False),
            },
        )

    connection.subscriptions[msg["id"]] = hass.bus.async_listen(EVENT_UPDATED, updated)
    connection.send_result(msg["id"])


@callback
def async_register_commands(hass):
    for handler in (
        ws_list,
        ws_get,
        ws_control,
        ws_configure,
        ws_configure_bulk,
        ws_reorder,
        ws_history,
        ws_predict,
        ws_subscribe,
    ):
        websocket_api.async_register_command(hass, handler)


async def async_setup_panel(hass):
    data = hass.data[DOMAIN]
    async with data.setdefault("panel_setup_lock", asyncio.Lock()):
        await _async_setup_panel(hass)


async def _async_setup_panel(hass):
    data = hass.data[DOMAIN]
    if "panel_state" not in data:
        from homeassistant.helpers.storage import Store

        state = PanelState(Store(hass, 1, f"{DOMAIN}.panel"))
        # Publish only after loading, so websocket readers cannot see a partial state.
        await state.async_load()
        data["panel_state"] = state
    if not data.get("api_registered"):
        async_register_commands(hass)
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/cca_zaluzie/frontend",
                    str(Path(__file__).parent / "frontend"),
                    cache_headers=False,
                )
            ]
        )
        add_extra_js_url(hass, f"/cca_zaluzie/frontend/icons.js?v={VERSION}")
        data["api_registered"] = True
    if not data.get("panel_registered"):
        await async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="cca-zaluzie-panel",
            sidebar_title="CCA Žalúzie",
            sidebar_icon="cca:day-night-blinds",
            module_url=f"/cca_zaluzie/frontend/cca-zaluzie-panel.js?v={VERSION}",
            require_admin=True,
            config_panel_domain=DOMAIN,
            config={"version": VERSION},
        )
        data["panel_registered"] = True
