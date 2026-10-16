# Overenie vydania 2026.12.0

Schválený redizajn je implementovaný v produkčnom paneli. Samostatný HTML návrh
zostáva historickou referenciou. Zachované sú identifikátory a nastavenia žalúzií,
bezpečnostná brána motorov, simulácia a reset s výdržou 60 sekúnd.

## Kontroly 16. októbra 2026

- Python 3.12: `py -3.12 -m pytest -q` — 151 passed, 4 skipped.
  Testy vyžadujúce skutočný HA runtime bežia na Linuxe v GitHub Actions.
- `py -3.12 -m ruff check custom_components tests` — bez chyby.
- `npm test` — 35 browser testov; produkčný modul so samostatnými fixtures.
  Prehliadač má explicitne nastavené pásmo Europe/Bratislava a locale sk-SK,
  aby časové očakávania nezáviseli od pásma počítača alebo CI runnera.
- Vizuálna kontrola produkčného prehľadu a mobilnej konfigurácie, bez pretečenia
  šírky pri 390 px; browser suite vytvára aj náhľady tmavej témy.
- `py -3.12 scripts/package_release.py 2026.12.0` — vytvorený HACS archív;
  skript overuje zhodu verzie a povinné súbory.
- Samostatné code review odhalilo a oprava s regresnými testami pokrýva otvorenie
  detailu novej live udalosti, zachovanie iba skutočných lokálnych úprav po bulk
  save a ochranu revision pred novšou cudzou konfiguráciou po uložení.
- Finálny vzdialený commit, CI a publikovaný archív sa overujú pri vydaní v PR #11.

## Aktualizácia a návrat

Pred aktualizáciou vytvor zálohu Home Assistanta. Nainštaluj vydanie cez HACS;
aktivácia vyžaduje používateľský reštart HA. Vývojové a release kontroly
neposielajú povely motorom a nereštartujú používateľov HA.

Konfiguračné kľúče, predvolené hodnoty a identity sa nemenia. Nové poradie panelu
a meraná história sú doplnkové údaje. Pri probléme obnov predchádzajúce vydanie
2026.11.1 cez HACS a reštartuj HA; pri potrebe úplného návratu použi zálohu.
