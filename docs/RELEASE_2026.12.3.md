# CCA Žalúzie 2026.12.3

Vydanie dokončuje issue [#13](https://github.com/denkz0ne/CCA_zaluzie/issues/13)
a dopĺňa ochranu kontaktu po zatvorení.

## Zmena pre používateľa

- Otvorený priechodový kontakt sa pri zapnutej ochrane potvrdí najneskôr za 2
  sekundy; zatvorenie naďalej rešpektuje nakonfigurované stabilizačné oneskorenie.
- Po potvrdenom zatvorení priechodového kontaktu sa na 30 minút zablokuje pohyb
  nadol. Ochrana sa ukladá a po otvorení alebo neznámom stave kontaktu sa
  znovu pripraví.
- Jednorazové manuálne **Zatvoriť** môže ochranu ukončiť iba pri aktuálne a
  stabilne potvrdenom zatvorenom kontakte. Posuvník, bežné klesajúce povely a
  Force-zatvorenie ju obísť nemôžu.
- Prehľad ukazuje zostávajúci čas a odložené vyhodnotenie. Ovládanie tlačidla
  zohľadňuje aj novšiu zmenu kontaktu, ktorú backend ešte nepotvrdil.
- Ochrana vypnutá pre danú žalúziu nevytvára nový časovač a nemení bežnú
  vetraciu logiku.
- Detailné správanie issue #13 a migráciu opisuje
  [Riadenie žalúzií](CONTROL_ENGINE.md).

## Kompatibilita a bezpečnostný rozsah

- Minimálna verzia Home Assistant: **2026.9.0**.
- Nové runtime polia majú bezpečné predvolené hodnoty pri načítaní starších dát.
- Zmeny sa overujú v testoch bez prístupu k nainštalovanému Home Assistantu a
  bez pohybu fyzických motorov.

## Overenie vydania

Lokálne overenie pred odovzdaním do GitHub CI:

- Python: **182 passed, 4 skipped**. Štyri HA lifecycle testy potrebujú Linuxové
  Home Assistant runtime; vykoná ich GitHub Actions.
- Browser: **38 passed** nad produkčným panelom a izolovanou testovacou zostavou.
- Ruff: všetky kontroly prešli.
- Prettier: kontrolované JS, CSS a browser testy sú naformátované.
- Release balík `cca_zaluzie.zip` sa zostavil a overila sa zhoda manifestu,
  panelu a tagovej verzie `2026.12.3`.

GitHub Actions, publikovaný tag/archív a uzavretie issue sa doplnia po
dokončení CI a zverejnení vydania.
