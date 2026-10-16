# Home Assistant panel redesign implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development. The user approved the HTML design and explicitly requested inline implementation through release; do not pause for another mockup or approval.

**Goal:** Deliver the approved HA-style panel, stable selection and order, visible last movement, understandable planned actions/history and safe selective bulk editing.

**Architecture:** Preserve the CCA evaluator and motor gateway. Add read-only presentation/history metadata in Python, a persisted panel order and a server-enforced bulk allowlist. Replace the production panel using the approved visual layout and actual HA controls, with portable fallbacks for browser tests. Split render/field/history helpers where useful.

**Tech Stack:** HA 2026.9+, Python 3.14 CI, vanilla ES modules, native HA selectors, pytest and Playwright.

**Spec:** `docs/ui/redesign-2026-10/README.md`, issue #10 and latest user additions (visible top-edge drag grip, last observed direction triangle, Ctrl/Cmd multi-selection, selective bulk edits, clearer Slovak terminology).

## Global constraints

- One controller and identity per cover. Preserve configured values, schedules, priorities, CCA mechanics, dry-run gateway and reset safety.
- Minimum Home Assistant 2026.9. No infrastructure restart or direct live HA deployment is authorized in this task.
- Planned actions are conditional descriptions, not another motor engine. Manual expiry alone does not authorize movement when `manual_return` is false.
- Persist measured history with explicit gaps. Never turn simulated/estimated position into measured history or a measured direction.
- Bulk edits patch only explicitly modified allowlisted keys after validating every candidate, with stale-config detection; protect identifiers, all entity/sensor fields, name/type, physical targets/calibration and nested action/condition editors.
- Main terminology: “manuálne ovládanie”, “ochrana manuálneho ovládania”, “čas otvorenia/zatvorenia” or “najskôr/najneskôr”; no unexplained “časové okno”.

## Review focus

- Reload/reconnect/null controller events must not change selected IDs or erase drafts; only explicit removal may choose a replacement.
- Reordering must persist, show a visible top grip/drop target, work by keyboard and provide a touch-friendly fallback; dragging must not toggle multi-selection.
- A bulk submission must not copy mixed or unchanged values, protected fields or another device's entities, and must reject stale revisions before any write.
- Unknown feedback must render a gap and keep controls safe; arrow direction must come from confirmed observed numeric changes.
- HA component availability must not break the entire panel; tooltips/field labels, keyboard navigation, mobile and theme colors must remain usable.

## Task 1 — Live presentation and history

Owner: presentation implementer. Files: `presentation.py`, controller/model extensions, focused pure/HA tests.

- [ ] Write meaningful failing tests for 18:30→19:00 manual protection with return on/off; unknown condition times; observed direction; measured history gaps and simulation isolation.
- [ ] Add `next_action`, `explanation`, `last_movement`, and `position_history` to controller snapshot. History points: `{at, position, available}`; last movement `{direction: opening|closing, at}` only for real measured deltas. Next action uses `{action,label,target,at,scheduled_at,earliest,latest,status,blocked_by,blocked_until,detail}`.
- [ ] Persist bounded position points and direction with existing controller storage; include real prior measured events where available. Provide async history read for 6/24/168 hours, optionally real Recorder data using verified API and stored fallback.
- [ ] Run focused tests and report interfaces/results.

## Task 2 — Persisted order and selective bulk API

Owner: API implementer. Files: `panel_state.py`, `bulk.py`, `api.py`, minimal `__init__.py` lifecycle changes, focused tests.

- [ ] Write failing validation/order/revision tests first.
- [ ] `list` returns `order`, `order_revision`, `fields[key].bulk_editable`, controllers with `config_revision` (stable hash of normalized config).
- [ ] `cca_zaluzie/reorder`: `{entry_ids,revision}` returns `{order,order_revision}`; persist in HA Store. Subscription accepts order-only updates. Distinguish explicit `removed:true` from transient reload absence.
- [ ] `cca_zaluzie/configure_bulk`: `{entry_ids,patch,revisions}` returns `{saved:true,configs:{id:config}}`. Explicit allowlist; normalize and validate all, then native validate all, then update. Lock mutations and reject any stale revision before writes. Single configure accepts optional expected revision too.
- [ ] `cca_zaluzie/history`: `{entry_id,hours:6|24|168}` calls presentation controller async history method and returns `{points,events,start,end}`.
- [ ] Run focused tests and report interfaces/results.

## Task 3 — Production panel

Owner: frontend implementer. Files: production frontend JS/CSS/helpers, `tests/browser/demo.html` and browser tests.

- [ ] Add failing browser regressions for selection stability, top-edge reorder, multi-selection/selective patch, protected fields, history, automatic next action and toast expiration.
- [ ] Port approved layout; all nine categories and concise summary. Main switches on top, suitable time/duration/percent/number/multi controls, native searchable entity pickers and conditions/actions; tooltips throughout. Preserve existing config drafts and safety/control features.
- [ ] Remove prediction calls/UI; simulation controls settings-only with visible read-only overview status. Read live history and new presentation metadata; no fixture data or invented motor times in production.
- [ ] Add visible grip top strip (grip dots + hover/focus label + grab cursor), drag/drop indicator and keyboard/touch ordering, persistence API. Ctrl/Cmd multiselect and touch checkbox; mixed values untouched unless explicitly edited; disabled protected fields; clear bulk confirmation count/result.
- [ ] Render confirmed last direction triangle above/below cover icon, accessible label/time; never infer from a requested target.
- [ ] Run browser tests and report outcomes.

## Task 4 — Copy, integration, review and release

Owner: root. Files: config metadata/localization/build metadata, docs/changelog/version, integration refinements and regression tests.

- [ ] Improve field names/help without changing keys/defaults or mechanics. Preserve dynamic position flow translations when rebuilding metadata.
- [ ] Integrate all contracts and assess validation, save/reload/order race behavior, native component fallbacks, all 162 fields, mobile/theme, reset and simulations.
- [ ] Run suitable Python/browser/lint/packaging checks once integrated; final independent code review and CI HA 2026.9/2026.10 plus HACS/hassfest.
- [ ] Update issue #10 and PR #11 to final implementation scope and latest additions. User authorized merge and release; merge only green reviewed code, publish version/tag/asset, verify publication, then close issues. No live HA restart.
