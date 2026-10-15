"""Durable panel ordering with serialized optimistic updates."""

from __future__ import annotations

import asyncio


class PanelState:
    """One shared order independent of config-entry loading/reloading."""

    def __init__(self, store):
        self.store = store
        self.order = []
        self.revision = 0
        self.lock = asyncio.Lock()

    async def async_load(self):
        stored = await self.store.async_load() or {}
        order = stored.get("order", [])
        if isinstance(order, list) and all(isinstance(item, str) for item in order):
            self.order = list(dict.fromkeys(order))
        revision = stored.get("order_revision", 0)
        if type(revision) is int and revision >= 0:
            self.revision = revision

    def snapshot(self, loaded_ids):
        loaded = list(loaded_ids)
        return {
            "order": [key for key in self.order if key in loaded]
            + [key for key in loaded if key not in self.order],
            "order_revision": self.revision,
        }

    async def async_reorder(self, entry_ids, revision, loaded_ids):
        async with self.lock:
            loaded = list(loaded_ids())
            if revision != self.revision:
                raise ValueError("Poradie sa medzitým zmenilo; obnov zobrazenie")
            if len(entry_ids) != len(set(entry_ids)) or set(entry_ids) != set(loaded):
                raise ValueError("Poradie musí obsahovať každú načítanú žalúziu práve raz")
            result = {"order": list(entry_ids), "order_revision": self.revision + 1}
            # Preserve unloaded entries in storage through temporary options reloads.
            stored = {
                **result,
                "order": list(entry_ids) + [key for key in self.order if key not in entry_ids],
            }
            await self.store.async_save(stored)
            self.order = stored["order"]
            self.revision = result["order_revision"]
            return result
