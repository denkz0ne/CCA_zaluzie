# Issue #17 — oprava dodaného panelu

## Porovnanie so zadaním z issues #10, #13 a #17

Používateľ 16. 10. 2026 odmietol výsledok 2026.12.4. Issue #17 sa znovu otvára;
predchádzajúce funkčné testy neoverili skutočný vzhľad po aktualizácii.

| Požiadavka | Overený problém v 2026.12.4 | Oprava a overenie |
| --- | --- | --- |
| Kompaktné karty s názvom, polohou a stavom | Nový JS používa neverzované `panel.css`. Reprodukcia s CSS 2026.12.3: grip vyplní 165 px vysokú kartu a názov je mimo orezaného rámčeka. | Verzovať CSS spolu s modulom; otestovať upgrade so starým CSS, rozmery a viditeľnosť celého obsahu. |
| Nenápadný úchyt hore, iba presúvanie | Staré CSS presunie úchyt do bežného toku a zakryje obsah. | Tenká horná úchopová plocha, grab/grabbing, klávesnica a zachované poradie. |
| Force štart/koniec tienenia a vetrania pri ovládaní | Akcie majú triedu `phase-action`, CSS očakáva `.motor.phase-action`. Vetranie vyzerá ako text. Chýba pomenovaná sekcia a samostatná dvojica štart/koniec. | Viditeľná sekcia pod posuvníkom, dva režimy, dvojice tlačidiel s ikonami, stavom a tooltipmi. Vypnuté možnosti vysvetliť, neschovávať bez dôvodu. |
| Jednorazovo posunúť začiatok alebo koniec režimu | Zachovať existujúce `phase_shade_start/end`, `phase_vent_start/end`, nie fyzický shortcut do polohy ani perzistentný Force prepínač. | Skontrolovať phase-latches a ich hranice, opakovanie plánov, bezpečnosť, vzájomné čakanie a zajtrajší plán. |
| Realtime bez preblikávania | Existuje patchovanie DOM, ale testy nezachytili zmiešané assety a časť ovládačov pri opakovaných aktualizáciách. | Séria 100 push zmien, identita prvkov, smer aj merané percentá v detaile a zozname, zachovanie rozpracovanej polohy a dialogu. |
| Zrozumiteľné názvy | Predikčné `close` je už preložené; preveriť ostatné runtime/phase identifikátory. | Slovenské názvy aj pre jednorazové fázy; žiadne surové kľúče v bežnom prehľade. |

Dodatočná kontrola odhalila aj vyprázdnenie obsahu otvoreného detailu pri
aktualizácii. Test teraz porovnáva celý obsah detailu pred a po push udalosti;
panel ponechá aktívny dialóg aj jeho obsah bez prerenderovania.

## Detská — nesprávna fyzická poloha

Read-only MCP kontrola: ZHA cover aj CCA snapshot hlásili 0 %, zdroj bol
`current_position`. Po čítaní Zigbee atribútu polohy ZHA hlásilo 100 %.
Používateľ potvrdil, že nesprávnu polohu zobrazovala aj samotná entita.
Nejde o dôkaz obrátených percent v CCA; integrácia nesmie nahradiť hlásenú
polohu cieľom ani ju bezdôvodne invertovať. Nebol odoslaný motorový povel.

## Akceptácia pred opätovným uzavretím

- [x] Upgrade s uloženým starým CSS stále zobrazí celé kompaktné karty.
- [x] Spustiť a ukončiť každý režim je zreteľné tlačidlo pri hlavnom ovládaní.
- [x] Vypnutý režim má viditeľný dôvod nedostupnosti.
- [x] Jednorazové akcie nahradia príslušný prechod, ďalší deň má vlastný plán.
- [x] Priebežné hodnoty a smer sa menia bez výmeny stabilných prvkov.
- [x] Desktop, mobil a tmavá téma sú skontrolované na produkčnom paneli.
- [x] Testy a GitHub CI prešli, dokumentácia je aktualizovaná a nový release balík je pripravený.

Publikácia sa overuje samostatne cez [vydanie 2026.12.5](https://github.com/denkz0ne/CCA_zaluzie/releases/tag/2026.12.5)
a záverečný komentár issue #17; lokálny zelený test sám osebe neznamená nasadenie.

Kontrola živého HA bola iba na čítanie; bez Chrome a bez reštartu.

Lokálne overenie: 185 Python testov prešlo, 4 HA moduly sa bez HA runtime preskočili;
58 browser testov prešlo. Ruff a Prettier prešli. Desktop, mobil (390 px) a tmavá
téma boli prezreté zo skutočného produkčného komponentu; bez chýb konzoly a overflow.

GitHub CI: [Tests](https://github.com/denkz0ne/CCA_zaluzie/actions/runs/38925577082)
— **256 Python testov** na každej HA verzii 2026.9.4 / 2026.10.0 / 2026.10.1,
**58 browser testov**. [Validate](https://github.com/denkz0ne/CCA_zaluzie/actions/runs/38925577070)
— HACS a hassfest prešli. Oprava je v [PR #20](https://github.com/denkz0ne/CCA_zaluzie/pull/20).
