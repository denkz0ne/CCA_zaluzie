# CCA Žalúzie 2026.12.8

## Oprava

Neznámy okenný/dverový kontakt blokoval v 2026.12.7 aj pohyb žalúzie nahor. Ranný plán mohol správne určiť cieľ 100 %, ale žiadny motorový povel sa neposlal.

Teraz sa pri tejto blokácii povolí pohyb iba vtedy, keď meraná poloha a cieľ preukazujú smer k otvoreniu podľa nastavených koncových polôh a tolerancie. Ostatné pravidlá riadenia sa naďalej overujú. Zatváranie, Force-close, neznáma poloha a nepreukázaný bezpečný smer zostávajú chránené. Ochrana otvoreného priechodu a 30-minútová ochrana po zatvorení sa nemenia.

Bez zásahu do ZHA, kalibrácie, invertovania polohy alebo nastavení jednotlivých žalúzií. Bez migrácie konfigurácie a histórie.

## Aktualizácia

Minimum HA 2026.9.0. Aktualizácia cez HACS, aktivácia po manuálnom reštarte HA. Živá inštalácia sa v rámci tejto opravy nemenila ani nereštartovala a motorové povely sa neposielali. Návrat na 2026.12.7 nevyžaduje migráciu; vracia však pôvodnú chybu blokovania otvárania.

Regresie preverujú neznámy/nedostupný kontakt, oba smery číselnej orientácie, polohu bez spätnej väzby, plne otvorenú polohu aj zachovanie ochrany pri zatváraní. CI a publikovaný ZIP sú doložené v nadväzujúcom issue/PR.
