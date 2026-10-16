# Riadenie žalúzií — verzia 2026.12.4

Tento dokument opisuje správanie verzie **2026.12.4**. Každá žalúzia má vlastný
stav a rozhodnutie. Automatizácia, prehľad najbližšieho pohybu aj simulácia
vychádzajú z rovnakého rozhodovacieho jadra. Predikcia nemení stav ani neposiela
povely; simulácia používa oddelený uložený stav a nevolá služby motora.

## Poradie rozhodovania

1. Integrácia načíta požadované vstupy a vyhodnotí plán, tienenie, vetranie,
   prítomnosť, manuálnu ochranu, Force a pauzu.
2. Tienenie a vetranie sú výlučné fázy. Rozbehnutá fáza sa dokončí; druhá čaká.
   Otvorenie bežného vetracieho kontaktu počas tienenia samo osebe tienenie
   nepreruší.
3. Ochrana kontaktu a pauza môžu pohyb zablokovať. Neznámy alebo nedostupný
   kontakt nedáva povolenie na nebezpečné zatvorenie. Pri aktívnej pauze sa
   motorový povel neodošle ani pri Force.
4. Pred odoslaním povelu sa aktuálne rozhodnutie a bezpečnostné podmienky znovu
   skontrolujú. Zmena cieľa alebo blokácie čakajúci povel zruší.

Force si mimo výslovne uvedenej bezpečnostnej výnimky zachováva doterajšie
správanie. Pri zapnutej ochrane priechodového kontaktu má bezpečnosť prednosť
pred Force-zatvorením.

## Kontakty, vetranie a ochrana po zatvorení

- Nové otvorenie priechodového kontaktu sa potvrdzuje najviac **2 sekundy**,
  nezávisle od starších dlhších nastavení. Ochranná/vetracia poloha tak môže
  reagovať rýchlo.
- Zatvorenie si ponecháva nastavené stabilizačné oneskorenie kontaktu. Až po
  jeho uplynutí sa zatvorený kontakt považuje za potvrdený.
- Ak je zapnutá ochrana priechodového kontaktu, po potvrdenom prechode
  otvorené → zatvorené beží **30-minútová ochrana proti klesaniu**. Zostáva
  uložená aj po reštarte HA. Ochrana sa okamžite znovu pripraví, keď sa kontakt
  otvorí alebo prestane byť známy.
- Počas ochrany automatika nevykoná pohyb smerom nadol. Rovnako sú zablokované
  posuvník polohy a bežné príkazy na nižšiu polohu, vrátane Force-zatvorenia.
- Používateľ môže ochranu jednorazovo ukončiť výslovným tlačidlom **Zatvoriť**,
  ale iba ak je aktuálny kontakt stále zatvorený a toto zatvorenie už bolo
  stabilne potvrdené. Novšia zmena kontaktu tlačidlo zablokuje, kým sa zatvorenie
  znovu nepotvrdí. Po úspešnom odoslaní manuálneho povelu sa udalosť zaznamená.
- Ak je ochrana vypnutá, nový 30-minútový časovač sa nezakladá. Bežná vetracia
  logika zostáva zachovaná. Voliteľný druhý kontakt je naďalej kompatibilný.

Najbližšia akcia v prehľade počas tejto ochrany ukazuje najskorší čas, keď sa
môže odložené zatvorenie znovu vyhodnotiť; nie je to prísľub pohybu, ak budú
vtedy aktívne iné podmienky alebo blokácie.

## Plán, tienenie a režimy

- Ranný a večerný plán používa nastavené časové okno Early/Late, výšku slnka,
  pracovné a voľné dni a zvolené podmienky. Neznáme budúce vstupy sa v predikcii
  označujú ako predpoklady; nevydávajú sa za potvrdenú udalosť.
- Ak potvrdené ranné otvorenie a začiatok tienenia vychádzajú do interného
  **30-minútového intervalu**, logický ranný cieľ sa splní a blízke pohyby sa
  zlúčia. Interval nie je používateľské nastavenie a zlúčenie nesmie preskočiť
  bezpečnostnú podmienku ani garantovanú hranicu plánu.
- Tienenie používa nastavenú čiastočnú výšku celej žalúzie a zvolené podmienky
  počasia, teploty, jasu alebo ďalších vstupov. Stabilizácia vybraného počasia je
  interná. Neznámy vstup ostáva konzervatívny.
- Jednorazové tlačidlá začať/ukončiť tienenie alebo vetranie nastavia hranicu
  aktuálnej fázy. Nezamykajú žalúziu natrvalo na cieľovej polohe.
- Manuálna korekcia cieľa je obmedzená na **±20 percentuálnych bodov** od
  pôvodného cieľa aktívneho režimu. **120 sekúnd** sa počíta od prvej prijatej
  úpravy; ďalšie úpravy čas nepredlžujú.

## Stav po reštarte a kompatibilita

Runtime sa ukladá so stabilným potvrdením kontaktu, časom ochrany a stavom jej
jednorazového uvoľnenia. Staršie uložené záznamy bez týchto polí sa načítajú s
bezpečnými predvolenými hodnotami. Migrácia nemení identitu žalúzie ani jej
konfigurované entity. Počas migrácie sa nevykonáva pohyb.

Minimálna verzia Home Assistant zostáva **2026.9.0**. Vývojová a integračná
validácia tejto verzie sa vykonáva v izolovaných testoch; toto vydanie samo osebe
neaktualizuje ani nereštartuje používateľov Home Assistant.



## Panel a živý stav pohybu — 2026.12.4

Panel používa stabilné uzly DOM a pri WebSocket aktualizáciách mení iba rozdiely.
Výber, otvorené okno detailu, fokus, rozpracované nastavenia a pozícia v zozname
prežijú aktualizáciu stavu. Smer aktívneho pohybu pochádza z reálneho stavu HA
cover entity alebo z prebiehajúceho povelu; simulácia je označená osobitne.
Cieľ pohybu sa nikdy nezapisuje do nameranej polohy. Po nečinnosti sa smerová
značka nezobrazuje len na základe historického posledného pohybu.

Zoznam používa kompaktné karty s úchytom na presúvanie, klávesnicovým
preusporiadaním a výberom viacerých kariet podržaním na dotykovom zariadení.
Tienenie a vetranie možno spustiť alebo ukončiť vedľa hlavných tlačidiel
ovládania; volanie služby naďalej prechádza existujúcou bezpečnostnou bránou.
