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

Lokálne overenie:

- Python: **182 passed, 4 skipped**. Štyri HA lifecycle testy potrebujú Linuxové
  Home Assistant runtime; vykoná ich GitHub Actions.
- Browser: **38 passed** nad produkčným panelom a izolovanou testovacou zostavou.
- Ruff: všetky kontroly prešli.
- Prettier: kontrolované JS, CSS a browser testy sú naformátované.
- Release balík `cca_zaluzie.zip` sa zostavil a overila sa zhoda manifestu,
  panelu a tagovej verzie `2026.12.3`.

Pull request [#15](https://github.com/denkz0ne/CCA_zaluzie/pull/15) bol zlúčený
do `main` commitom `b81db54`; issue [#13](https://github.com/denkz0ne/CCA_zaluzie/issues/13)
sa uzavrelo pri merge. CI na finálnom kóde prešlo: HA **2026.9.4**,
**2026.10.0**, **2026.10.1**, browser suite, Ruff, hassfest a HACS.

Vydanie [`2026.12.3`](https://github.com/denkz0ne/CCA_zaluzie/releases/tag/2026.12.3)
bolo publikované úspešným release workflow. Stiahnutý `cca_zaluzie.zip` má 34
súborov, manifest verzie `2026.12.3` a produkčný panel.

SHA-256 publikovaného archívu:

```text
471dd738ab63f8b6fa8578029ab09caa802ce4ca7d0cf7ad3a8d7df02ec75ed6
```
