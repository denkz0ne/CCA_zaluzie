# CCA Žalúzie 2026.12.9

## Spresnené pravidlo používateľa

Dverový/okenný senzor bez platného binárneho stavu sa má správať ako nepriradený. `unknown`, `unavailable`, chýbajúca entita a iný neplatný stav preto neblokujú otvorenie ani zatvorenie a nevytvárajú kontaktnú ochranu. Staré kontaktné časovače a potvrdenia sa pri ignorovaní vyčistia.

Senzor sa nevymaže z konfigurácie. Po návrate platného `on`/`off` sa automaticky znova použije. Platný otvorený kontakt a následná ochrana po potvrdenom zatvorení zostávajú funkčné.

Toto je náhrada za užšiu opravu 2026.12.8, ktorá povoľovala iba bezpečný smer otvárania. Rovnaké pravidlo platí pre automatiku, manuálne ovládanie a výpočet scenárov; ignorovanie je uvedené v detailoch rozhodnutia. Ostatné podmienky, ochrana manuálneho ovládania a potreba dostupnej polohy žalúzie sa nemenia.

## Aktualizácia

Minimum HA 2026.9.0. Aktualizácia cez HACS a následný manuálny reštart HA. Bez migrácie, zmien ZHA, kalibrácie či prepísania konfigurácie senzorov. Živý HA sa v rámci dodávky nemení ani nereštartuje; motorové povely sa neposielajú.

Návrat na 2026.12.8 vráti blokovanie zatvárania pri neznámom kontakte. Výsledky CI a kontrola publikovaného balíka sú v nadväzujúcom PR/issue.
