# CCA Žalúzie identity

User-approved concept **02** from the final day/night proposal sheet (2026-10-11).
Day and night occupy the upper half equally; the lower half represents the shutter.
Colors: amber `#FFC857`, night navy `#123C55`, Home Assistant cyan `#18BCF2`, white.
Flat fills, transparent surrounding canvas, no texture or gradient.

- `custom_components/cca_zaluzie/brand/icon.svg`: editable color vector.
- `brand/icon.png` and `brand/icon@2x.png`: 256/512 px integration assets.
- `frontend/icon.svg`: monochrome vector with transparent cutouts.
- `frontend/icons.js`: same geometry for `cca:day-night-blinds`, using HA's current color.
- `scripts/build_brand.mjs`: reproducible SVG/PNG generation with Playwright.

Home Assistant 2026.3+ discovers custom-integration images in the local `brand/`
directory. This project requires 2026.10+. No external brand-catalog submission
is needed. Source: [HA brand-image documentation](https://developers.home-assistant.io/docs/core/integration/brand_images/).

The icon module is registered as a global extra frontend module so the sidebar
can draw the monochrome icon before the CCA panel is opened. The panel imports
the same path; all monochrome uses inherit theme color rather than hardcoding black.

This is an original integration mark, not an official Home Assistant logo.
