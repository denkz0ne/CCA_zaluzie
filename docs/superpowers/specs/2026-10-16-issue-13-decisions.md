# Issue #13 implementation decisions

## Confirmed by the user on 2026-10-16

1. Manual corrections use a limit of **±20 percentage points** from the original mode target and a **120-second edit period**, started by the first accepted correction. Later corrections do not extend the period; the corrected target remains for the phase.
2. If morning opening and shading are calculated within **30 minutes**, allow morning to be fulfilled logically and merge/coalesce the movements. This interval is internal, not a new user-facing setting. Never merge across a safety constraint or a hard schedule guarantee; uncertain future conditions do not count as a confirmed event.
3. Ventilation and shading are mutually exclusive. The active phase finishes before the other phase starts; do not replace or overlap an active phase.
4. For the fourth answer, the user selected the first Force/contact option: **on a cover configured as a passage/terrace contact with lockout enabled, contact safety takes priority over Force-close**. This is a scoped safety rule, not approval to reorder all Force priorities. Legacy Force entities and their semantics remain supported elsewhere.

## Conservative rulings where no answer was supplied

- Keep existing manual-override expiry, reset, return, schedule adoption and blocking behavior until an explicit mapping is approved; do not invent a new auto-return.
- Preserve all existing configuration values during migration. No permanent field removal without a field-by-field audit, safe migration and approval; explicitly approved morning/evening lux and calendar behavior can be retired only after compatibility is implemented and documented.
- A contact configured only for ordinary ventilation does not gain the terrace post-close lockout.
- Preserve all selectable supported weather states; stabilization is internal and uses selection membership.

## Safety and release boundary

- Runtime evaluation, overview/next-action prediction and dry-run must consume the same decision result. Prediction stays read-only; dry-run never calls motor services.
- Unknown/unavailable passage contact blocks potentially dangerous closing. The scoped Force exception must be tested against open, unknown and closed contact states.
- No live Home Assistant access, deployment, restart, or physical motor operation is part of this repository release.
- Keep the current HA minimum and release process unless issue #13 explicitly requires a change.

