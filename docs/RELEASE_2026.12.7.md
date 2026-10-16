# CCA Žalúzie 2026.12.7

## Zmeny

Schválený graf je zapracovaný priamo do integrácie: jednoduchá čiara meranej polohy, vyplnená žltá krivka dňa nad nulou a modrá krivka noci pod nulou. Obe používajú rovnaké časy. Rozsah je posledných 24 hodín, bez prepínačov, bodiek, zoomu a číselných stupníc. Neznáme meranie zostáva medzerou.

Pod grafom je posledných 20 užitočných udalostí. Opakované technické vyhodnotenia a samotné prepočty sa v prehľade nezobrazujú; skutočné zmeny režimu alebo ochrany zostávajú. Úplný dostupný záznam vrátane technických udalostí a oddelenej simulácie je cez odkaz dole. Každá udalosť má detail.

Slnko sa počíta podľa lokality HA a zobrazuje sa v časovom pásme HA. Výška krivky je orientačná; stupne slnka sa nestotožňujú s percentami žalúzie. Nie je potrebné pridávať senzor.

## Aktualizácia a návrat

Minimum HA 2026.9.0. Bez zmeny schémy konfigurácie alebo uložených dát, identity či mechaniky pohybu. Aktualizácia cez HACS a následný manuálny reštart HA. Návrat na 2026.12.6 je možný bez migrácie histórie. Táto dodávka nemení ani nereštartuje živý HA.

## Overenie

Výsledky aktuálneho GitHub CI a kontrola publikovaného ZIP budú zaznamenané v nadväzujúcom PR a issue. Vizuálna kontrola používa produkčný panel s oddelenými ukážkovými údajmi, nie živé motorové povely.
