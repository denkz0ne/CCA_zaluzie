# CCA Žalúzie 2026.12.5

Oprava skutočných odchýlok od issues #10, #13 a znovuotvoreného #17.
Porovnanie požiadaviek, príčin a regresných kontrol je v
[audite dodaného panelu](ISSUE_17_DELIVERY_AUDIT.md).

## Zmeny

- CSS preberá verziu JS modulu. Staré uložené štýly po aktualizácii nezakryjú
  názvy a polohy v kartách automatizácií.
- Pod posuvníkom sú štyri zreteľné tlačidlá štartu/konca tienenia a vetrania,
  s ikonami, stavom a vysvetlením jednorazového účinku. Vypnutý režim má dôvod.
- Priebežné percentá a smer sa aktualizujú bez výmeny stabilných ovládačov.
  Aktívny HA posuvník, atribúty HA komponentov, obsah otvoreného detailu a značka
  presúvania sa zachovajú.
- Výpočet ďalšieho pohybu reaguje hneď na režim či ochranu; samotné percentá
  počas jazdy nespúšťajú opakovane predikciu na dva dni.
- Nedostupná žalúzia nemá aktívnu šípku zo starého povelu. Cieľ nie je meranie.

## Overenie

Regresie overujú upgrade so starým CSS, rozmery a obsah kariet, štyri phase
príkazy, 100 priebežných aktualizácií, zachovanie posuvníka a presúvania,
obnovenie predikcie a nedostupnosť. Engine testy overujú skorší štart,
prevzatie plánovaného začiatku, prirodzený koniec, potlačenie dnešného opakovania,
nasledujúci deň a nový vetrací cyklus. HA testy sledujú reálne odosielanie
snapshotov pri začiatku, priebehu a skončení pohybu.

GitHub CI: **256 Python testov prešlo** na každej HA verzii 2026.9.4,
2026.10.0 a 2026.10.1; **58 browser testov prešlo**. Ruff, hassfest a HACS prešli.
[Tests](https://github.com/denkz0ne/CCA_zaluzie/actions/runs/38925577082) ·
[Validate](https://github.com/denkz0ne/CCA_zaluzie/actions/runs/38925577070) ·
[PR #20](https://github.com/denkz0ne/CCA_zaluzie/pull/20).
Záverečný výsledok je v issue [#17](https://github.com/denkz0ne/CCA_zaluzie/issues/17).

## Aktualizácia a návrat

Minimum je Home Assistant **2026.9.0**. Identita, konfigurácia a runtime schéma
sa nemenia. Aktualizuj integráciu cez HACS a reštartuj HA, keď sa rozhodneš.
CSS už nevyžaduje ručné mazanie cache pri bežnej aktualizácii panelu.
Na návrat možno cez HACS zvoliť 2026.12.4; tá však obsahuje zdokumentovanú
regresiu štýlov. Pred zmenou verzie zachovaj vlastnú zálohu konfigurácie.

Release: [2026.12.5](https://github.com/denkz0ne/CCA_zaluzie/releases/tag/2026.12.5).
Kontrola živého HA bola iba na čítanie; bez Chrome, reštartu a motorových povelov.
