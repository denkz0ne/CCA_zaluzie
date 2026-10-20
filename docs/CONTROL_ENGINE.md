# Riadenie žalúzií — verzia 2026.12.9

Tento dokument opisuje správanie verzie **2026.12.9**. Každá žalúzia má vlastný
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



## Panel a živý stav pohybu — 2026.12.6

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

V 2026.12.6 sú štart a koniec samostatné tlačidlá v sekcii pod posuvníkom.
Začiatok na pokyn nahradí plánovaný začiatok aktuálnej fázy; režim potom skončí
podľa svojich pravidiel. Ukončenie tienenia zabráni jeho dnešnému opakovaniu.
Ukončenie vetrania potlačí aktuálny kontaktný cyklus; nový cyklus môže začať
ďalšie vetranie. Platnosť hraníc sa nemení na trvalý Force stav.
Pri strate dostupnosti snapshot výslovne označí pohyb ako nedostupný,
nezachová aktívny smer zo starého povelu a nevymýšľa nameranú polohu.

## Okná a ochrana priechodu — 2026.12.6

V konfigurácii vyber **Okná a vetranie → Ochrana priechodu**. Veľký prepínač
chráni priechod pri otvorenom okne alebo dverách a ešte 30 minút po potvrdenom
zatvorení. Vyžaduje zapnuté spracovanie kontaktov a bežný kontakt otvorenia.
Vypnutím ochrany sa kontakt používa na vetranie; nejde o vypnutie celého riadenia.
Ochranná poloha sa naďalej nastavuje medzi cieľovými polohami žalúzie.

Vyklopené okno už nemá vlastný senzor, nastavenia ani vetvu rozhodovania či
predikcie. Migrácia na schému vstupu 1.3 odstráni šesť starých nastavení bez
premapovania na kontakt otvorenia. Identita žalúzie a ostatné parametre ostanú.
Starý runtime vyklopenia a jeho korekcia sa vyčistia; migrácia neposiela povel
motoru. Pri ďalšom bežnom vyhodnotení platia aktuálne pravidlá automatizácie.
Vetranie, jeho jednorazový štart/koniec, korekcie ±20 percentuálnych bodov počas
120 sekúnd a bezpečnostné blokovanie Force pri otvorenom kontakte zostávajú.

## História a udalosti — 2026.12.7

Prehľad má jeden pevný graf za posledných 24 hodín, bez prepínačov, bodiek, zoomu
a číselných stupníc. Tenká tyrkysová čiara zobrazuje výhradne namerané polohy.
Neznáme polohy a nedostupnosť prerušia čiaru; cieľ ani simulácia nie sú meranie.
Krivka slnka je vypočítaná z polohy HA v rovnakých časoch: žltá výplň nad
horizontom, modrá pod ním. Výplne končia na spoločnej nulovej čiare. Výška
krivky je orientačná; neporovnáva stupne s percentami žalúzie. Časová os je
spoločná, rešpektuje časové pásmo HA a zmenu dňa aj letného času. Geometria
slnka nevyžaduje nastavený senzor ani nemení žiadnu automatizačnú podmienku.

Pod grafom je posledných 20 užitočných fyzických udalostí: motorové výsledky,
odoslané povely, manuálne ovládanie, zmeny režimu a bezpečnostných blokácií,
reset, chyby. Opakované vyhodnotenia s rovnakým režimom a blokáciou, samotný
prepočet a príprava povelu prehľad nezahlcujú. Zmena režimu či blokácie sa
zobrazí aj vtedy, keď jej zdrojom bolo vyhodnotenie. Záznamy sa nemažú.

**Zobraziť úplný záznam a detaily →** otvorí všetky dostupné uložené udalosti
vrátane technických vyhodnotení. Simulácia zostáva oddelená a má filter.
Každá udalosť má detail s časom, typom a pôvodnými údajmi; odtiaľ sa dá
vrátiť na úplný zoznam. Úplný znamená údaje uchované podľa nastavených
limitov histórie, nie neobmedzený archív.

## Neznámy kontakt a bezpečné otváranie — 2026.12.8

Neznámy alebo nedostupný kontakt už neblokuje pohyb, ktorý z nameranej polohy
preukázateľne smeruje k otvorenej polohe. Smer vychádza z nastavených
`open_position`/`close_position` a tolerancie, nie z predpokladu, že vyššie číslo
vždy znamená otvorenie. Ostatné blokácie, manuálna ochrana, denné limity
a podmienky zostávajú v platnosti.

Zatváranie pri neznámom kontakte je naďalej blokované, vrátane Force-close.
Ak chýba potvrdená poloha alebo cieľ, bezpečný smer nie je preukázaný a
blokácia zostáva. Ochrana otvoreného priechodu a 30-minútová ochrana po
zatvorení sa nemenia. Nie je potrebné vypínať kontakt ani meniť ZHA či
kalibráciu, aby sa táto oprava uplatnila.

## Aktuálne pravidlo kontaktu — 2026.12.9

Používateľ spresnil pravidlo: priradený dverový/okenný kontakt s neznámym,
nedostupným, chýbajúcim alebo neplatným binárnym stavom sa počas daného
vyhodnotenia správa **ako nepriradený**. Neblokuje ani otvorenie, ani
zatvorenie a nevytvára ochranu priechodu. Predchádzajúci časovač kontaktnej
ochrany a kontaktné potvrdenia sa pri jeho ignorovaní vyčistia. Záznam
`contact.ignored` zachová dôvod v detailoch, prehľad neukazuje chybu kontaktu.

Výber senzora zostáva uložený a odber zmien zostáva aktívny. Keď senzor
znovu hlási platný binárny stav (`on`/`off` alebo ekvivalent otvorené/zatvorené),
integrácia ho automaticky znova použije. Platné otvorenie naďalej chráni
priechod; platné zatvorenie používa potvrdenie a 30-minútovú ochranu.
Toto pravidlo nahrádza užšie pravidlo verzie 2026.12.8 popísané vyššie.

Ignoruje sa iba voliteľný kontakt, nie meranie polohy samotnej žalúzie,
manuálna ochrana ani používateľské podmienky či ostatné senzory riadenia.
Nastavenia a runtime schéma sa nemenia, nie je potrebné odpájať ani
prekalibrovať ZHA zariadenie.
