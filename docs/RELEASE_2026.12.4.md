# CCA Žalúzie 2026.12.4

Published **2026-10-16** from commit [`9caf942`](https://github.com/denkz0ne/CCA_zaluzie/commit/9caf942b5e3107ada7a977d08438f53e290f4605).
The release resolves [issue #17](https://github.com/denkz0ne/CCA_zaluzie/issues/17)
through [PR #18](https://github.com/denkz0ne/CCA_zaluzie/pull/18).

## Changes

- Live updates patch the panel in place, preserving focus, editing drafts,
  selected covers, dialogs, scrolling and recorded SVG nodes. Identical
  snapshots that only advance the server clock do not trigger a render.
- Active opening and closing are based on the current Home Assistant cover
  state or accepted command. The target stays separate from measured position;
  requested commands and simulation are clearly distinguished.
- The automation list uses compact cards and an accessible drag grip, retains
  keyboard reordering and supports touch long-press multi-selection.
- Shading and ventilation phase actions sit beside primary position controls;
  action labels use readable Slovak names.

## Verification

- GitHub Actions passed for Home Assistant **2026.9.4**, **2026.10.0** and
  **2026.10.1**, browser tests, HACS validation and hassfest:
  [CI run](https://github.com/denkz0ne/CCA_zaluzie/actions/runs/38909371763).
- Release packaging and publication succeeded:
  [release workflow](https://github.com/denkz0ne/CCA_zaluzie/actions/runs/38909691261).
- Local Playwright suite: **46 passed**. Ruff, Prettier, Python syntax
  compilation and `git diff --check` passed.

Installable archive: [`cca_zaluzie.zip`](https://github.com/denkz0ne/CCA_zaluzie/releases/download/2026.12.4/cca_zaluzie.zip)  
SHA-256: `cf6d97e04a9ae88ea6b5e3e421033f95a627217fe4fc765d50da8e441e2da848`
