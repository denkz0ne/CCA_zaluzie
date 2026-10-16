"""Pure regression tests for selective bulk transactions and panel ordering."""

import asyncio
from types import MappingProxyType

import pytest

from custom_components.cca_zaluzie.bulk import (
    BULK_EDITABLE,
    async_save_configs,
    config_revision,
    prepare_bulk,
)
from custom_components.cca_zaluzie.config import FIELDS, validate_config
from custom_components.cca_zaluzie.panel_state import PanelState


def config(**values):
    return validate_config({"cover_entity": "cover.test", **values})


def test_bulk_allowlist_excludes_every_physical_identity_and_native_editor():
    for key, field in FIELDS.items():
        if field.kind in ("entity", "condition", "action", "text"):
            assert key not in BULK_EDITABLE
    assert (
        not {
            "enabled",
            "cover_type",
            "position_source",
            "position_source_auto",
            "drive_time",
            "open_position",
            "manual_reset_position",
            "custom_action_only",
        }
        & BULK_EDITABLE
    )
    assert {"morning_early_free", "manual_timeout", "shade_start_and", "debug"} <= BULK_EDITABLE


def test_revision_accepts_home_assistant_read_only_entry_data():
    original = config()
    assert config_revision(MappingProxyType(original)) == config_revision(original)


def test_revision_is_normalized_and_mapping_order_independent():
    assert config_revision({"cover_entity": "cover.test"}) == config_revision(config())
    assert config_revision(config()) == config_revision(dict(reversed(list(config().items()))))
    assert config_revision(config()) != config_revision(config(debug=True))


def test_bulk_keeps_individual_values_and_rejects_bad_candidate_and_revision():
    configs = {"a": config(name="A"), "b": config(name="B", morning_early="07:00")}
    revisions = {key: config_revision(value) for key, value in configs.items()}
    result = prepare_bulk(configs, ["a", "b"], {"debug": True}, revisions)
    assert result["a"]["name"] == "A"
    assert result["b"]["morning_early"] == "07:00"
    with pytest.raises(ValueError):
        prepare_bulk(configs, ["a", "b"], {"morning_late": "06:45"}, revisions)
    with pytest.raises(ValueError):
        prepare_bulk(configs, ["a", "b"], {"cover_entity": "cover.other"}, revisions)
    with pytest.raises(ValueError):
        prepare_bulk(configs, ["a", "b"], {"debug": True}, {**revisions, "b": "old"})


def test_native_validation_failure_and_concurrent_change_write_nothing():
    async def run():
        originals = {"a": config(), "b": config(name="B")}
        candidates = {key: {**cfg, "debug": True} for key, cfg in originals.items()}
        writes = []

        async def invalid(cfg):
            if cfg["name"] == "B":
                raise ValueError("native invalid")

        with pytest.raises(ValueError):
            await async_save_configs(
                candidates,
                originals,
                lambda key: originals[key],
                invalid,
                lambda key, cfg: writes.append(key),
            )
        assert writes == []

        async def changed(cfg):
            originals["b"] = config(name="changed")

        before = dict(originals)
        with pytest.raises(ValueError):
            await async_save_configs(
                candidates,
                before,
                lambda key: originals[key],
                changed,
                lambda key, cfg: writes.append(key),
            )
        assert writes == []

    asyncio.run(run())


def test_order_is_persistent_revision_checked_and_failed_save_keeps_state():
    class Store:
        data = None
        fail = False

        async def async_load(self):
            return self.data

        async def async_save(self, value):
            if self.fail:
                raise OSError("disk failure")
            self.data = value

    async def run():
        store = Store()
        state = PanelState(store)
        await state.async_load()
        assert state.snapshot(["a", "b"])["order"] == ["a", "b"]
        assert await state.async_reorder(["b", "a"], 0, lambda: ["a", "b"]) == {
            "order": ["b", "a"],
            "order_revision": 1,
        }
        restored = PanelState(store)
        await restored.async_load()
        assert restored.snapshot(["a", "b"]) == state.snapshot(["a", "b"])
        for ids, revision in [(["a", "b"], 0), (["a"], 1), (["a", "a"], 1)]:
            with pytest.raises(ValueError):
                await state.async_reorder(ids, revision, lambda: ["a", "b"])
        store.fail = True
        with pytest.raises(OSError):
            await state.async_reorder(["a", "b"], 1, lambda: ["a", "b"])
        assert state.snapshot(["a", "b"])["order"] == ["b", "a"]

    asyncio.run(run())


def test_concurrent_reorder_has_one_winner_and_preserves_unloaded_identity():
    class Store:
        async def async_load(self):
            return {"order": ["a", "b", "temporarily_unloaded"], "order_revision": 3}

        async def async_save(self, value):
            await asyncio.sleep(0)
            self.data = value

    async def run():
        store = Store()
        state = PanelState(store)
        await state.async_load()
        results = await asyncio.gather(
            state.async_reorder(["b", "a"], 3, lambda: ["a", "b"]),
            state.async_reorder(["a", "b"], 3, lambda: ["a", "b"]),
            return_exceptions=True,
        )
        assert sum(isinstance(result, ValueError) for result in results) == 1
        assert state.revision == 4
        assert state.snapshot(["a", "b", "temporarily_unloaded"])["order"] == [
            "b",
            "a",
            "temporarily_unloaded",
        ]
        assert store.data["order"][-1] == "temporarily_unloaded"

    asyncio.run(run())
