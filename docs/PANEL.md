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

Pod posuvníkom je sekcia **Jednorazové zmeny režimov**. Tienenie aj vetranie
majú vlastnú dvojicu tlačidiel s ikonou a stavom. **Spustiť teraz** posunie
začiatok aktuálneho režimu; pôvodný začiatok sa už nezopakuje. **Ukončiť**
posunie jeho koniec. Ukončené tienenie sa pri rovnakých podmienkach dnes
nespustí znova; ďalší deň má bežný plán. Ukončené vetranie sa neobnoví pri
rovnakom stave kontaktu, ale nový cyklus okna môže spustiť ďalšie vetranie.
Aktívny režim dobehne pred začiatkom druhého. Bezpečnostná ochrana priechodu
má naďalej prednosť. Tieto akcie nenastavujú trvalý Force prepínač.

Vypnuté režimy zostávajú viditeľné s neaktívnymi tlačidlami a dôvodom
**Vypnuté v konfigurácii**. Jednorazové presunutie iba do tieniacej alebo
vetracej polohy je samostatná sekundárna akcia pod históriou.

Od verzie 2026.12.5 sa štýly načítajú pod rovnakou verziou ako panel. Browser
preto po aktualizácii nepoužije staré pravidlá úchytu s novým obsahom kariet.
Prichádzajúce percentá nemenia rozpracovanú hodnotu zameraného posuvníka.
Predikcia sa obnoví pri zmene režimu alebo ochrany, nie pri každom percente jazdy.

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
