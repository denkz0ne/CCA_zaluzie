# CCA Žalúzie 2026.12.6

## Zmeny

- **Konfigurácia → Okná a vetranie → Ochrana priechodu** má vlastnú viditeľnú sekciu, prepínač a vysvetlenie ochrany pri otvorení aj 30 minút po zatvorení.
- Vyklopené okno je úplne vyradené z aktívnej konfigurácie, rozhodovania, predikcie a sledovaných vstupov. Zostáva jeden bežný kontakt otvorenia/zatvorenia.
- Schéma vstupu 1.3 odstráni `window_tilted`, `tilted_lockout`, `tilted_blocks`, `vent_keep_full_tilt`, `vent_lower_from_above`, `vent_after_shade`. Žiadny senzor sa automaticky nepremapuje.
- Starý runtime vyklopenia a jeho korekcie sa bezpečne vyčistia. Migrácia zachováva identitu a ostatné nastavenia a neposiela motorové povely. Následné bežné vyhodnotenie používa aktuálne pravidlá.
- Bežné vetranie a jednorazové ovládače zostávajú. Korekcie vetrania fungujú aj bez vyradeného senzora; ochrana priechodu sa nepovažuje za vetraciu korekciu.

## Aktualizácia

Minimum Home Assistant 2026.9.0. Aktualizuj cez HACS a následne reštartuj HA podľa vlastného rozhodnutia. Táto dodávka neinštaluje ani nereštartuje živý HA. Pred návratom na staršiu verziu zachovaj zálohu: odstránené nastavenia vyklopenia sa samy neobnovia.

Oprava issue #21. Testy a výsledky CI sú uvedené v nadväzujúcom PR a issue.
