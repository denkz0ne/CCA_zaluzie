# Overenie vydania 2026.12.2

Toto vydanie implementuje potvrdené rozhodnutia z issue #13 pre korekcie,
vzájomné vylúčenie tienenia a vetrania, zlúčenie ranného otvorenia s blízkym
tienením, stabilizáciu počasia a prioritu ochrany kontaktu pred Force-zatvorením.

## Lokálne kontroly 16. októbra 2026

- `py -3.12 -m pytest -q` — 169 passed, 4 skipped. Preskočené testy vyžadujú
  Home Assistant runtime, ktorý lokálne nie je nainštalovaný.
- `npm test` — 36 browser testov passed; vrátane nových tlačidiel režimových akcií.
- `py -3.12 -m ruff check custom_components tests` — všetky kontroly prešli.
- `git diff --check` — bez chýb formátu.
- `py -3.12 scripts/package_release.py 2026.12.2` — vytvorený HACS archív,
  verzia manifestu a povinné súbory overené.
- HA migračný test starého konfiguračného záznamu je pridaný, ale čaká na Linux
  GitHub Actions, pretože HA runtime testy sa lokálne preskočili.

## Aktualizácia a návrat

Konfiguračná migrácia presunie staré hodnoty do normalizovanej konfigurácie,
odstráni už nepoužívané ranné/večerné vstupy jasu a kalendára a ponechá starý
senzor jasu ako voliteľný vstup tienenia, ak nebol nastavený nový. Pred
aktualizáciou si urob zálohu Home Assistanta. Vydanie nebolo nainštalované do
živého Home Assistanta a motory neboli ovládané.

Pri probléme obnov vydanie 2026.12.1 cez HACS a reštartuj Home Assistant.
Konfiguračné hodnoty vyradené z plánovania sa pri obnove môžu vyžadovať zo zálohy.
