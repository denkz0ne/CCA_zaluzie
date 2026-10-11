"""Admin-only WebSocket panel API using the same live per-cover controller."""

from __future__ import annotations

from pathlib import Path

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.core import Context, callback

from .config import FIELDS, GROUPS, validate_config
from .config_flow import async_validate_native
from .const import DOMAIN, EVENT_UPDATED, PANEL_PATH, VERSION


def _controllers(hass):
    return hass.data[DOMAIN]["controllers"]


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
            "fields": {key: spec.public() for key, spec in FIELDS.items()},
            "controllers": [controller.snapshot() for controller in _controllers(hass).values()],
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "cca_zaluzie/get", vol.Required("entry_id"): str}
)
@websocket_api.require_admin
@callback
def ws_get(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        connection.send_result(msg["id"], controller.snapshot())


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
            await controller.async_control(
                msg["action"], msg.get("position"), context=Context(user_id=connection.user.id)
            )
            connection.send_result(msg["id"], controller.snapshot())
        except Exception as error:
            connection.send_error(msg["id"], "operation_failed", str(error))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "cca_zaluzie/configure",
        vol.Required("entry_id"): str,
        vol.Required("config"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_configure(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        try:
            config = validate_config(msg["config"], cover_entity=controller.config["cover_entity"])
            await async_validate_native(hass, config)
            hass.config_entries.async_update_entry(
                controller.entry, title=config["name"], options=config
            )
            connection.send_result(msg["id"], {"saved": True, "config": config})
        except Exception as error:
            connection.send_error(msg["id"], "invalid_config", str(error))


@websocket_api.websocket_command({vol.Required("type"): "cca_zaluzie/subscribe"})
@websocket_api.require_admin
@callback
def ws_subscribe(hass, connection, msg):
    @callback
    def updated(event):
        controller = _controllers(hass).get(event.data["entry_id"])
        connection.send_event(
            msg["id"],
            {
                "entry_id": event.data["entry_id"],
                "controller": controller.snapshot() if controller else None,
            },
        )

    connection.subscriptions[msg["id"]] = hass.bus.async_listen(EVENT_UPDATED, updated)
    connection.send_result(msg["id"])


@callback
def async_register_commands(hass):
    for handler in (ws_list, ws_get, ws_control, ws_configure, ws_subscribe):
        websocket_api.async_register_command(hass, handler)


async def async_setup_panel(hass):
    data = hass.data[DOMAIN]
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
        data["api_registered"] = True
    if not data.get("panel_registered"):
        await async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="cca-zaluzie-panel",
            sidebar_title="CCA Žalúzie",
            sidebar_icon="mdi:blinds-horizontal",
            module_url=f"/cca_zaluzie/frontend/cca-zaluzie-panel.js?v={VERSION}",
            require_admin=True,
            config_panel_domain=DOMAIN,
            config={"version": VERSION},
        )
        data["panel_registered"] = True
