# Panel CCA Žalúzie

## Bežné ovládanie

Vyber žalúziu v zozname. Prehľad rozlišuje potvrdenú polohu, cieľ a dôvod,
prečo automatika čaká. Tlačidlá otvorenia, STOP a zatvorenia ovládajú jednu
vybranú žalúziu. Režim simulácie má prepínač v konfigurácii; jeho aktívny stav
zostáva viditeľný aj v prehľade.

Vypočítaný ďalší pohyb používa aktuálny čas, polohu slnka, plán a produkčné
rozhodovanie integrácie. Prehľad ukazuje aktuálne hodnoty relevantných senzorov,
vypočítaný čas a hodnoty pri očakávanom pohybe vrátane azimutu a výšky slnka.
Stavy alebo hodnoty, ktoré v budúcnosti nemožno poznať, sú označené ako
predpoklady a výsledok ako podmienený scenár. Výpočet nemení runtime, históriu,
uložené nastavenia ani stav motora. Koniec ochrany manuálneho ovládania sám
nespustí návrat, pokiaľ nie je zapnuté obnovenie aktuálneho cieľa.

História používa namerané polohy a podľa dostupnosti aj Recorder. Neznáma
poloha je medzera v grafe. Simulácia ani časový odhad nevytvárajú namerané
polohy. Smerová značka pri ikone sa zobrazuje iba počas práve potvrdeného
pohybu. Cieľ pohybu je samostatný údaj a nemení potvrdenú polohu.

Pri zmene stavu sa panel aktualizuje bez výmeny celého zobrazenia. Otvorené
detaily, rozpracované nastavenia, výber žalúzií, posuvník aj pozícia zoznamu
zostanú zachované. Zoznam používa menšie karty a úchyt na hornej hrane; poradie
možno meniť potiahnutím alebo klávesmi hore/dole, Home a End. Ctrl/Cmd-kliknutie
vyberie viac položiek; na dotykovom zariadení podrž kartu približne pol sekundy.

Jednorazové začatie a ukončenie tienenia či vetrania je pri hlavných tlačidlách
otvorenia, zastavenia a zatvorenia. Jednorazové presunutie do tieniacej alebo
vetracej polohy zostáva medzi ďalšími akciami.

Keď je zapnutá ochrana kontaktu, otvorenie kontaktu po najviac dvojsekundovom
potvrdení presunie žalúziu do ochrannej polohy. Po potvrdenom zatvorení kontaktu
sa spustí 30-minútová ochrana pred automatickým zatvorením. Prehľad ukazuje
zostávajúci čas a plánované zatvorenie po jej skončení. Opätovné otvorenie
kontaktom túto ochranu zruší a spustí nový cyklus po ďalšom zatvorení.

Po návrate môže používateľ raz stlačiť **Zatvoriť** a ochranu ukončiť, ale iba
keď je kontakt aktuálne a stabilne zatvorený. Počas ochrany je posuvník polohy
zablokovaný; neznámy kontakt, Force-zatvorenie ani iný povel ju neobídu. Bez
zapnutej ochrany otvorený kontakt môže vyvolať bežné vetranie a 30-minútový
interval sa nepoužije.

## Poradie automatizácií

Na hornej hrane každej karty je zvýraznený úchyt. Potiahni ho na nové miesto;
značka vloženia ukáže výsledné umiestnenie. Poradie sa uloží pre panel. Na
klávesnici zameraj úchyt a použi šípky alebo Home/End. Na dotyk podrž kartu na
výber viacerých žalúzií.

## Hromadná úprava

Pomocou Ctrl/Cmd-kliknutia alebo podržania karty na dotykovej obrazovke vyber
viac žalúzií a otvor konfiguráciu.
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
