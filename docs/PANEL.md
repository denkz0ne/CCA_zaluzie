# Panel CCA Žalúzie

## Bežné ovládanie

Vyber žalúziu v zozname. Prehľad rozlišuje potvrdenú polohu, cieľ a dôvod,
prečo automatika čaká. Tlačidlá otvorenia, STOP a zatvorenia ovládajú jednu
vybranú žalúziu. Režim simulácie má prepínač v konfigurácii; jeho aktívny stav
zostáva viditeľný aj v prehľade.

Najbližšia akcia je zámer automatizácie. Ak závisí od budúceho svetla, okna
alebo inej podmienky, presný čas pohybu sa nesľubuje. Koniec ochrany manuálneho
ovládania sám nespustí návrat, pokiaľ nie je zapnuté obnovenie aktuálneho cieľa.

História používa namerané polohy a podľa dostupnosti aj Recorder. Neznáma
poloha je medzera v grafe. Simulácia ani časový odhad nevytvárajú namerané
polohy. Trojuholník pri ikone ukazuje posledný potvrdený smer pohybu.

## Poradie automatizácií

Na hornej hrane každej karty je zvýraznený pásik s bodkovaným úchytom.
Potiahni ho na nové miesto; značka vloženia ukáže výsledné umiestnenie.
Poradie sa uloží pre panel. Na klávesnici zameraj úchyt a použi šípky;
na dotykovej obrazovke môžeš použiť aj tlačidlá presunu.

## Hromadná úprava

Pomocou Ctrl/Cmd alebo zaškrtávacích polí vyber viac žalúzií a otvor konfiguráciu.
Rozdielne hodnoty sa zobrazia ako rôzne hodnoty. Uložia sa iba polia, ktoré
výslovne upravíš. Neupravené hodnoty zostanú každej žalúzii vlastné.

Spoločne možno upraviť časy pracovných a voľných dní, trvania, prahy, logické
pravidlá a záznamy. Názvy, typ, entity a senzory, fyzické cieľové polohy,
kalibrácia, zdroj polohy a vlastné akcie či podmienky sú chránené.
Simulácia a manuálne motorové povely zostávajú individuálne.

Pred uložením server overí všetky vybrané konfigurácie. Ak sa niektorá medzičasom
zmenila alebo je neplatná, celú hromadnú požiadavku odmietne pred prvým zápisom.
Obnov zobrazenie a skontroluj zmenené hodnoty.

## Obnovenie a uloženie

Rozpracované úpravy patria ku konkrétnej žalúzii. Aktualizácia stavov, preusporiadanie
alebo dočasný reload ich nemajú zahodiť. Skutočné vymazanie vybratej žalúzie
oznámi panel a zvolí ďalšiu dostupnú položku. Úspešné oznámenie sa zavrie po
štyroch sekundách; chyba zostane pri nastavení.

Aktualizácia integrácie nemení uložené entity, rozvrhy ani mechaniku CCA.
Home Assistant vyžaduje po nainštalovaní vydania používateľský reštart.
