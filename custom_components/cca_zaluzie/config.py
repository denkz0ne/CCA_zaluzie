"""Shared validated configuration and progressive UI field metadata."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import Any

GROUPS = {
    "cover": "Žalúzia",
    "schedule": "Ráno a večer",
    "light": "Svetlo a slnko",
    "shading": "Tienenie",
    "windows": "Okná a vetranie",
    "manual": "Manuálne ovládanie",
    "resident": "Režimy a obnova",
    "advanced": "Podmienky a akcie",
    "records": "Záznamy",
}


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    default: Any
    kind: str
    group: str
    help: str = ""
    options: tuple[str, ...] = ()
    minimum: float = 0
    maximum: float = 86400
    unit: str = ""
    depends: str = ""

    def public(self) -> dict:
        return asdict(self)


FIELDS: dict[str, Field] = {}
LEGACY_CONFIG_FIELDS = {
    # Read only as migration input; never expose or subscribe to these fields.
    "tilted_blocks",
    "tilted_lockout",
    "vent_after_shade",
    "vent_keep_full_tilt",
    "vent_lower_from_above",
    "window_tilted",

    "calendar_enabled",
    "calendar_entity",
    "calendar_open_title",
    "calendar_close_title",
    "lux_enabled",
    "lux_sensor",
    "lux_open",
    "lux_close",
    "lux_hysteresis",
    "lux_duration",
    "light_operator",
}


def _f(key, label, default, kind="number", group="cover", **kwargs):
    FIELDS[key] = Field(key, label, default, kind, group, **kwargs)


_f(
    "cover_entity",
    "Entita žalúzie",
    "",
    "entity",
    help="Jedna automatizácia ovláda presne jednu žalúziu.",
)
_f("name", "Názov", "Žalúzia", "text")
_f("enabled", "Povoliť automatizáciu", True, "bool")
_f(
    "cover_type",
    "Typ žalúzie",
    "blind",
    "select",
    options=("blind", "shutter", "awning", "sunshade"),
    help="Markíza a slnečná clona používajú obrátené cieľové polohy podľa CCA.",
)
_f(
    "position_source",
    "Zdroj polohy",
    "current_position",
    "select",
    options=("current_position", "position", "sensor", "drive_time"),
)
_f("position_sensor", "Vlastný senzor polohy", "", "entity")
for key, label, value in [
    ("open_position", "Otvorené", 100),
    ("close_position", "Zatvorené", 0),
    ("shade_position", "Tienenie", 58),
    ("vent_position", "Vetranie", 30),
    ("lockout_position", "Otvorené okno", 100),
    ("position_tolerance", "Tolerancia", 2),
]:
    _f(key, label, value, maximum=100, unit="%")
_f(
    "drive_time",
    "Čas úplnej jazdy",
    60,
    minimum=1,
    maximum=600,
    unit="s",
    help="Pri zariadení bez spätnej väzby ide o kalibrovaný čas jazdy. Odhad nie je nameraná poloha.",
)
_f("movement_timeout", "Čas na potvrdenie pohybu", 120, minimum=5, maximum=900, unit="s")

for key, label, value in [
    ("time_enabled", "Časové okná", True),
    ("morning_enabled", "Ranné otvorenie", True),
    ("evening_enabled", "Večerné zatvorenie", True),
]:
    _f(key, label, value, "bool", "schedule")
for prefix, label, early, late, free_early, free_late in [
    ("morning", "Ráno", "06:30", "08:00", "08:00", "09:30"),
    ("evening", "Večer", "18:00", "21:30", "18:30", "22:00"),
]:
    for suffix, text, value in [
        ("early", "najskôr · pracovný deň", early),
        ("late", "najneskôr · pracovný deň", late),
        ("early_free", "najskôr · voľný deň", free_early),
        ("late_free", "najneskôr · voľný deň", free_late),
    ]:
        _f(
            f"{prefix}_{suffix}",
            f"{label} {text}",
            value,
            "time",
            "schedule",
            depends="time_enabled",
        )
for key, label in [
    ("workday_sensor", "Pracovný deň dnes"),
    ("workday_tomorrow", "Pracovný deň zajtra"),
]:
    _f(key, label, "", "entity", "schedule")
_f("sun_enabled", "Používať výšku slnka", False, "bool", "light")
_f("sun_sensor", "Slnko", "sun.sun", "entity", "light")
_f(
    "sun_open",
    "Výška slnka na otvorenie",
    0,
    group="light",
    minimum=-90,
    maximum=90,
    unit="°",
    depends="sun_enabled",
)
_f(
    "sun_close",
    "Výška slnka na zatvorenie",
    -3,
    group="light",
    minimum=-90,
    maximum=90,
    unit="°",
    depends="sun_enabled",
)
_f("sun_open_sensor", "Vlastná hranica otvorenia", "", "entity", "light", depends="sun_enabled")
_f("sun_close_sensor", "Vlastná hranica zatvorenia", "", "entity", "light", depends="sun_enabled")
_f("sun_duration", "Potvrdenie výšky slnka", 30, group="light", unit="s", depends="sun_enabled")
_f(
    "sun_direction",
    "Smer pohybu slnka",
    "both",
    "select",
    "light",
    options=("both", "rising_falling"),
)

_f("shading_enabled", "Povoliť tienenie", False, "bool", "shading")
_f(
    "shade_ignore_time",
    "Tienenie aj mimo časového okna",
    False,
    "bool",
    "shading",
    depends="shading_enabled",
)
PREDICATES = (
    "azimuth",
    "elevation",
    "brightness",
    "temperature1",
    "temperature2",
    "forecast",
    "weather",
    "custom",
)
for key, label, value in [
    ("shade_start_and", "Začiatok · musia platiť všetky", ["azimuth", "elevation", "brightness"]),
    ("shade_start_or", "Začiatok · aspoň jedna", []),
    ("shade_end_and", "Ukončenie · musia platiť všetky", []),
    ("shade_end_or", "Ukončenie · aspoň jedna", ["azimuth", "elevation", "brightness"]),
]:
    _f(
        key,
        label,
        value,
        "multi",
        "shading",
        options=PREDICATES,
        depends="shading_enabled",
        help="Ak vyberieš skupinu AND aj OR, musia platiť všetky AND a aspoň jedna OR.",
    )
for key, label, value, maximum, unit in [
    ("shade_azimuth_start", "Azimut od", 95, 360, "°"),
    ("shade_azimuth_end", "Azimut do", 265, 360, "°"),
    ("shade_elevation_min", "Výška slnka od", 25, 90, "°"),
    ("shade_elevation_max", "Výška slnka do", 90, 90, "°"),
    ("shade_lux_start", "Jas na začiatok", 35000, 200000, "lx"),
    ("shade_lux_end", "Jas na ukončenie", 25000, 200000, "lx"),
    ("shade_lux_hysteresis", "Hysterézia jasu tienenia", 1000, 10000, "lx"),
    ("shade_start_delay", "Potvrdenie začiatku", 300, 86400, "s"),
    ("shade_end_delay", "Potvrdenie ukončenia", 300, 86400, "s"),
    ("shade_start_max", "Najdlhšie opakovanie začiatku", 3600, 86400, "s"),
    ("shade_end_max", "Najdlhšie opakovanie ukončenia", 3600, 86400, "s"),
]:
    _f(key, label, value, group="shading", maximum=maximum, unit=unit, depends="shading_enabled")
for key, label in [
    ("shade_lux_sensor", "Jas pre tienenie"),
    ("temperature_sensor1", "Teplota 1"),
    ("temperature_sensor2", "Teplota 2"),
    ("forecast_entity", "Predpoveď počasia"),
    ("forecast_temp_sensor", "Vlastná predpovedaná teplota"),
    ("shade_custom_sensor", "Vlastná podmienka"),
    ("shade_alt_entity", "Spínač alternatívneho tienenia"),
]:
    _f(key, label, "", "entity", "shading", depends="shading_enabled")
for key, label, value in [
    ("temperature1_min", "Hranica teploty 1", 25),
    ("temperature2_min", "Hranica teploty 2", 25),
    ("forecast_min", "Hranica predpovede", 25),
    ("shade_independent_temp", "Nezávislá teplotná hranica", 25),
    ("temperature1_hysteresis", "Hysterézia teploty 1", 1),
    ("temperature2_hysteresis", "Hysterézia teploty 2", 1),
    ("forecast_hysteresis", "Hysterézia predpovede", 1),
]:
    _f(
        key,
        label,
        value,
        group="shading",
        minimum=-50,
        maximum=100,
        unit="°C",
        depends="shading_enabled",
    )
_f("forecast_type", "Typ predpovede", "daily", "select", "shading", options=("daily", "hourly"))
_f(
    "shade_weather",
    "Podmienky počasia",
    ["sunny", "partlycloudy"],
    "multi",
    "shading",
    options=(
        "clear-night",
        "cloudy",
        "fog",
        "hail",
        "lightning",
        "lightning-rainy",
        "partlycloudy",
        "pouring",
        "rainy",
        "snowy",
        "snowy-rainy",
        "sunny",
        "windy",
        "windy-variant",
        "exceptional",
    ),
)
for key, label in [
    ("shade_independent", "Nezávislé tienenie podľa teploty"),
    ("shade_compare_sensor2", "Zohľadniť teplotu 2 nezávisle"),
    ("shade_hold_hot", "Pri vysokej teplote udržať tienenie"),
    ("shade_end_immediate", "Ukončiť ihneď mimo slnečného rozsahu"),
]:
    _f(key, label, False, "bool", "shading", depends="shading_enabled")
_f("shade_alt_position", "Alternatívna poloha tienenia", 45, group="shading", maximum=100, unit="%")

_f(
    "ventilation_enabled",
    "Povoliť vetranie a kontakty",
    False,
    "bool",
    "windows",
    help="Pri vypnutí sa kontakty ignorujú aj pri blokovaní zatvorenia.",
)
_f("window_open", "Kontakt otvoreného okna", "", "entity", "windows", depends="ventilation_enabled")
_f(
    "contact_lockout_enabled",
    "Ochrana priechodu",
    True,
    "bool",
    "windows",
    depends="ventilation_enabled",
)
_f(
    "contact_delay",
    "Potvrdenie spúšťača kontaktu",
    2,
    group="windows",
    unit="s",
    depends="ventilation_enabled",
)
_f(
    "contact_state_delay",
    "Oneskorenie stavu kontaktu",
    3,
    group="windows",
    unit="s",
    depends="ventilation_enabled",
)
_f("shading_over_ventilation", "Uprednostniť tienenie pred vetraním", False, "bool", "windows")

_f("manual_enabled", "Rozpoznať ručný pohyb", True, "bool", "manual")
_f(
    "manual_blocks",
    "Ručný režim blokuje",
    ["open", "close", "shade_start"],
    "multi",
    "manual",
    options=("open", "close", "ventilate", "shade_start", "shade_end"),
)
_f("manual_reset_time", "Ukončiť ručný režim každý deň o", "00:01", "time", "manual")
_f("manual_reset_daily", "Použiť denné ukončenie", True, "bool", "manual")
_f(
    "manual_timeout",
    "Ukončiť po uplynutí času",
    10800,
    group="manual",
    unit="s",
    help="0 vypne ukončenie podľa trvania.",
)
_f("manual_reset_position_enabled", "Ukončiť pri dosiahnutí polohy", False, "bool", "manual")
_f(
    "manual_reset_position",
    "Poloha ukončenia ručného režimu",
    100,
    group="manual",
    maximum=100,
    unit="%",
)
_f("manual_position_dwell", "Výdrž polohy pred ukončením", 300, group="manual", unit="s")
for key, label, default in [
    ("manual_return", "Po ukončení nastaviť aktuálny cieľ", False),
    ("manual_adopt_open", "Ručné otvorenie uznáva ranný plán", True),
    ("manual_adopt_close", "Ručné zatvorenie uznáva večerný plán", True),
    ("force_recovery", "Po vynútenom povele obnoviť cieľ", True),
]:
    _f(key, label, default, "bool", "manual")
for suffix, label in [
    ("open", "otvorenie"),
    ("close", "zatvorenie"),
    ("ventilate", "vetranie"),
    ("shade", "tienenie"),
    ("pause", "pauzu"),
]:
    _f(f"force_{suffix}", f"Entita vynucujúca {label}", "", "entity", "manual")

_f("resident_sensor", "Spánok / prítomnosť obyvateľa", "", "entity", "resident")
for key, label, default in [
    ("resident_close", "Pri aktivácii zatvoriť", False),
    ("resident_open", "Po ukončení povoliť otvorenie", False),
    ("resident_allow_open", "Povoliť otvorenie počas režimu", False),
    ("resident_allow_shade", "Povoliť tienenie počas režimu", True),
    ("resident_allow_vent", "Povoliť vetranie počas režimu", True),
    ("recovery_enabled", "Obnoviť cieľ po výpadku dostupnosti", False),
    ("startup_recovery", "Po štarte obnoviť vypočítaný cieľ", False),
]:
    _f(key, label, default, "bool", "resident")
_f("instance_entity", "Entita povoľujúca automatizáciu", "", "entity", "resident")
_f("instance_value", "Povoľujúci stav", "on", "text", "resident")

_f("drive_delay", "Oneskorenie pred pohybom", 0, group="advanced", maximum=600, unit="s")
_f("drive_random", "Dodatočné náhodné oneskorenie", 0, group="advanced", maximum=600, unit="s")
_f(
    "custom_action_only",
    "Pohyb iba vlastnými akciami",
    False,
    "bool",
    "advanced",
    help="Namiesto štandardného povelu použije nakonfigurované akcie. Reset vždy používa štandardné close/stop služby.",
)
_f("global_conditions", "Spoločné podmienky pohybu", [], "condition", "advanced")
for event, label in [
    ("open", "Otvorenie"),
    ("close", "Zatvorenie"),
    ("ventilate", "Vetranie"),
    ("ventilate_end", "Koniec vetrania"),
    ("shade_start", "Začiatok tienenia"),
    ("shade_end", "Koniec tienenia"),
]:
    _f(f"{event}_conditions", f"{label} · podmienky", [], "condition", "advanced")
    _f(f"{event}_before", f"{label} · akcie pred pohybom", [], "action", "advanced")
    _f(f"{event}_after", f"{label} · akcie po pohybe", [], "action", "advanced")
for event, label in [("manual", "Ručný zásah"), ("manual_reset", "Koniec ručného režimu")]:
    _f(f"{event}_after", f"{label} · akcie", [], "action", "advanced")
_f("debug", "Podrobné vyhodnotenia", False, "bool", "records")
_f("logbook", "Zapisovať do záznamníka", True, "bool", "records")
_f("logbook_cover", "Priradiť záznamy k žalúzii", True, "bool", "records")
_f(
    "retention_days",
    "Uchovávanie udalostí",
    30,
    group="records",
    minimum=1,
    maximum=365,
    unit="dní",
)
_f("history_limit", "Najviac uložených udalostí", 2000, group="records", minimum=100, maximum=10000)


_f(
    "sun_threshold_mode",
    "Výpočet hranice výšky slnka",
    "fixed",
    "select",
    "light",
    options=("fixed", "dynamic", "hybrid"),
    help="Pevná hranica, hodnota senzora alebo senzor plus pevný posun.",
)
for key, label, group in [
    ("open_once", "Otvoriť automaticky iba raz denne", "schedule"),
    ("close_once", "Zatvoriť automaticky iba raz denne", "schedule"),
    ("shade_once", "Začať tienenie iba raz denne", "shading"),
    ("prevent_higher_close", "Pri večernom zatvorení nezdvíhať", "cover"),
    ("prevent_lower_close_shaded", "Večer zachovať výšku tienenia", "cover"),
    ("prevent_shade_end_closed", "Neukončiť tienenie už zatvorenej žalúzie", "shading"),
    ("prevent_open_shade_end", "Po tienení neotvárať", "shading"),
    ("prevent_open_vent_end", "Po vetraní neotvárať", "windows"),
    ("vent_start_no_delay", "Vetranie bez oneskorenia jazdy", "windows"),
    ("vent_return_delay", "Po zatvorení okna použiť oneskorenie jazdy", "windows"),
]:
    _f(key, label, False, "bool", group)
FIELDS["forecast_type"] = Field(
    "forecast_type",
    "Zdroj predpovede",
    "daily",
    "select",
    "shading",
    options=("daily", "hourly", "weather_attributes"),
    help="Denná/hodinová predpoveď používa prvý platný zvolený interval. Atribúty počasia používajú aktuálnu teplotu a stav.",
)


# Keep presentation copy separate from persisted configuration keys and defaults.
_LABELS = {
    "time_enabled": "Používať čas otvorenia a zatvorenia",
    "shade_ignore_time": "Tieniť aj mimo bežného času",
    "lux_hysteresis": "Rozdiel jasu na zrušenie podmienky",
    "shade_lux_hysteresis": "Rozdiel jasu na zrušenie podmienky tienenia",
    "temperature1_hysteresis": "Rozdiel teploty 1 na zrušenie podmienky",
    "temperature2_hysteresis": "Rozdiel teploty 2 na zrušenie podmienky",
    "forecast_hysteresis": "Rozdiel predpovede na zrušenie podmienky",
    "shade_azimuth_start": "Smer slnka od",
    "shade_azimuth_end": "Smer slnka do",
    "manual_enabled": "Chrániť manuálne ovládanie",
    "manual_blocks": "Počas ochrany odložiť tieto akcie",
    "manual_reset_time": "Každý deň ukončiť ochranu o",
    "manual_reset_daily": "Ukončiť ochranu každý deň",
    "manual_timeout": "Dĺžka ochrany po manuálnom ovládaní",
    "manual_reset_position": "Poloha na ukončenie ochrany",
    "manual_return": "Po skončení ochrany obnoviť aktuálny cieľ",
    "manual_adopt_open": "Manuálne otvorenie splní ranný plán",
    "manual_adopt_close": "Manuálne zatvorenie splní večerný plán",
    "manual_after": "Manuálne ovládanie · následné akcie",
    "manual_reset_after": "Koniec ochrany manuálneho ovládania · následné akcie",
}
_HELP = {
    "name": "Názov, pod ktorým sa žalúzia zobrazí v paneli a nastaveniach.",
    "enabled": "Zapne automatické vyhodnocovanie. Po vypnutí môžeš žalúziu naďalej ovládať manuálne.",
    "position_source": "Určuje, odkiaľ integrácia číta polohu. Automatický výber ponúkne toto nastavenie až pri probléme so spätnou väzbou.",
    "position_sensor": "Senzor s číselnou polohou od 0 do 100 percent, ak ju samotná žalúzia neposkytuje.",
    "position_tolerance": "Rozdiel polohy v percentuálnych bodoch, ktorý sa ešte považuje za dosiahnutý cieľ.",
    "movement_timeout": "Ako dlho po povele čakať na potvrdenie pohybu alebo dosiahnutie cieľa.",
    "time_enabled": "Použije nižšie zadané časy ranného otvorenia a večerného zatvorenia. Podmienky svetla a ostatné ochrany zostávajú súčasťou rozhodovania.",
    "morning_enabled": "Povolí ranné automatické otvorenie podľa nastavených časov a podmienok.",
    "evening_enabled": "Povolí večerné automatické zatvorenie podľa nastavených časov a podmienok.",
    "workday_sensor": "Senzor pracovného dňa určí dnešné časy. Bez neho sú sobota a nedeľa voľné dni.",
    "workday_tomorrow": "Senzor pracovného dňa zajtra umožní večer zohľadniť nasledujúci deň.",
    "calendar_entity": "Kalendár s udalosťami, ktoré určujú čas otvorenia alebo zatvorenia.",
    "calendar_enabled": "Pri plánovaní použije udalosti zo zvoleného kalendára s uvedenými názvami.",
    "calendar_open_title": "Názov kalendárovej udalosti, ktorej začiatok určí čas otvorenia.",
    "calendar_close_title": "Názov kalendárovej udalosti, ktorej začiatok určí čas zatvorenia.",
    "lux_enabled": "Otvorenie a zatvorenie bude zohľadňovať nameraný jas a dobu jeho potvrdenia.",
    "lux_open": "Jas, pri ktorom možno ráno otvoriť. Vyššia hodnota vyžaduje viac denného svetla.",
    "lux_close": "Jas, pri ktorom možno večer zatvoriť. Vyššia hodnota dovolí zatvorenie ešte za väčšieho svetla.",
    "lux_hysteresis": "Rezerva v jase zabraňuje opakovanému zapínaniu a rušeniu podmienky pri malých výkyvoch.",
    "lux_duration": "Ako dlho musí jas spĺňať podmienku, kým sa uzná za potvrdenú.",
    "sun_enabled": "Otvorenie a zatvorenie bude zohľadňovať výšku slnka nad obzorom.",
    "sun_open": "Výška slnka pre ranné otvorenie; záporná hodnota znamená slnko pod obzorom.",
    "sun_close": "Výška slnka pre večerné zatvorenie; záporná hodnota znamená slnko pod obzorom.",
    "sun_duration": "Ako dlho musí výška slnka spĺňať podmienku, kým sa uzná za potvrdenú.",
    "sun_direction": "Vyber, či sa má zohľadniť aj stúpanie slnka ráno a klesanie večer.",
    "sun_threshold_mode": "Použije pevnú výšku slnka, hodnotu vybraného senzora alebo hodnotu senzora upravenú o pevný posun.",
    "light_operator": "Pri voľbe všetkých podmienok musí vyhovovať jas aj slnko; pri voľbe aspoň jednej stačí jedna z nich.",
    "shading_enabled": "Povolí automatické tienenie podľa nižšie vybraných podmienok.",
    "shade_ignore_time": "Dovolí vyhodnocovať tienenie aj mimo bežného času medzi ranným otvorením a večerným zatvorením.",
    "shade_start_delay": "Ako dlho musia platiť podmienky začiatku tienenia pred jeho spustením.",
    "shade_end_delay": "Ako dlho musia platiť podmienky ukončenia tienenia pred jeho ukončením.",
    "shade_start_max": "Najdlhšie obdobie pokusov o potvrdenie začiatku tienenia. Po prekročení sa čaká na nový cyklus podmienok; 0 obmedzenie vypne.",
    "shade_end_max": "Najdlhšie obdobie pokusov o potvrdenie konca tienenia. Po prekročení sa čaká na nový cyklus podmienok; 0 obmedzenie vypne.",
    "shade_azimuth_start": "Začiatok rozsahu smerov slnka, ktoré dopadajú na okno: sever 0°, východ 90°, juh 180°, západ 270°.",
    "shade_azimuth_end": "Koniec rozsahu smerov slnka dopadajúcich na okno. Rozsah môže prechádzať cez sever.",
    "shade_lux_start": "Hranica jasu na začatie tienenia, ak je jas vybraný medzi podmienkami.",
    "shade_lux_end": "Hranica jasu na ukončenie tienenia, ak je jas vybraný medzi podmienkami.",
    "shade_weather": "Stavy počasia, pri ktorých vyhovuje podmienka počasia pre tienenie.",
    "shade_independent": "Dovolí samostatné tienenie podľa teplotnej hranice aj bez bežnej kombinácie podmienok tienenia.",
    "shade_compare_sensor2": "Pri nezávislom tienení zohľadní aj druhý teplotný senzor.",
    "shade_hold_hot": "Pri pretrvávajúcej vysokej teplote zachová tienenie aj po skončení ostatných podmienok.",
    "shade_end_immediate": "Po opustení nastaveného rozsahu slnka ukončí tienenie bez bežného potvrdzovacieho čakania.",
    "contact_delay": "Krátke čakanie po zmene okenného kontaktu pred vyhodnotením; potlačí rýchle opakované zmeny.",
    "contact_lockout_enabled": "Pri otvorenom okne alebo dverách drží žalúziu v bezpečnej polohe. Po potvrdenom zatvorení chráni priechod ešte 30 minút. Vypnutím tejto ochrany kontakt slúži iba na vetranie.",
    "contact_state_delay": "Ako dlho musí nový stav kontaktu zostať stabilný, kým sa použije pri riadení.",
    "shading_over_ventilation": "Pri súčasne aktívnom tienení a vetraní uprednostní polohu tienenia, pri zachovaní ochrany kontaktov.",
    "open_once": "Po splnení ranného otvorenia ho v ten istý deň znovu automaticky neopakuje.",
    "close_once": "Po splnení večerného zatvorenia ho v ten istý deň znovu automaticky neopakuje.",
    "shade_once": "Po začatí tienenia ho v ten istý deň znovu automaticky nespustí.",
    "prevent_higher_close": "Večerné zatvorenie nesmie pohnúť žalúziou smerom k otvoreniu, ak už je viac zatvorená než nastavený cieľ.",
    "prevent_lower_close_shaded": "Ak večerný plán ukončí aktívne tienenie, zabráni ďalšiemu pohybu smerom k zatvoreniu.",
    "prevent_shade_end_closed": "Ukončenie tienenia nepohne žalúziou, ktorá už dosiahla zatvorenú polohu.",
    "prevent_open_shade_end": "Po skončení tienenia zabráni návratu smerom k otvorenej polohe.",
    "prevent_open_vent_end": "Po skončení vetrania zabráni návratu smerom k otvorenej polohe.",
    "vent_start_no_delay": "Pri začiatku vetrania vynechá bežné pevné a náhodné oneskorenie pred pohybom.",
    "vent_return_delay": "Pri návrate po zatvorení okna použije bežné oneskorenie pred pohybom.",
    "manual_enabled": "Po zistení manuálneho ovládania odloží vybrané automatické akcie, aby neprepísali tvoju polohu.",
    "manual_blocks": "Vyber, ktoré automatické akcie majú počas ochrany manuálneho ovládania čakať.",
    "manual_timeout": "Ako dlho chrániť polohu po manuálnom ovládaní. Hodnota 0 vypne ukončenie podľa trvania.",
    "manual_reset_daily": "Ukončí ochranu manuálneho ovládania každý deň vo vybranom čase.",
    "manual_reset_time": "Denný čas ukončenia ochrany, ak je zapnuté jej každodenné ukončenie.",
    "manual_reset_position_enabled": "Ukončí ochranu po dosiahnutí vybranej polohy a uplynutí doby jej potvrdenia.",
    "manual_reset_position": "Poloha, ktorej dosiahnutie môže ukončiť ochranu manuálneho ovládania.",
    "manual_position_dwell": "Ako dlho musí žalúzia zostať vo vybranej polohe pred ukončením ochrany.",
    "manual_return": "Po skončení ochrany znovu overí podmienky a dovolí pohyb na aktuálny cieľ. Pri vypnutí samotné skončenie ochrany pohyb nespustí.",
    "manual_adopt_open": "Manuálne otvorenie na cieľovú polohu v čase ranného otvárania uzná ako splnený ranný plán.",
    "manual_adopt_close": "Manuálne zatvorenie na cieľovú polohu v čase večerného zatvárania uzná ako splnený večerný plán.",
    "force_recovery": "Po skončení vynúteného povelu znovu vyhodnotí bežný cieľ automatizácie.",
    "resident_sensor": "Entita aktivujúca osobitný režim, napríklad spánok alebo prítomnosť. Jej aktívny stav obmedzí nižšie vybrané akcie.",
    "resident_close": "Pri aktivácii osobitného režimu dovolí zatvorenie, ak je povolené večerné zatváranie.",
    "resident_open": "Po skončení osobitného režimu dovolí znovu vyhodnotiť otvorenie podľa aktuálnych podmienok.",
    "resident_allow_open": "Dovolí automatické otvorenie aj počas aktívneho osobitného režimu.",
    "resident_allow_shade": "Dovolí automatické tienenie aj počas aktívneho osobitného režimu.",
    "resident_allow_vent": "Dovolí automatické vetranie aj počas aktívneho osobitného režimu.",
    "recovery_enabled": "Po návrate dostupnosti zariadenia dovolí obnoviť aktuálne vypočítanú polohu.",
    "startup_recovery": "Po štarte Home Assistanta dovolí obnoviť aktuálny cieľ. Vypnuté nastavenie počká na ďalšiu bežnú udalosť.",
    "instance_entity": "Automatizácia smie vykonať pohyb iba vtedy, keď má táto entita nižšie uvedený stav.",
    "instance_value": "Presný stav povoľujúcej entity, pri ktorom je automatický pohyb povolený.",
    "drive_delay": "Pevné čakanie pred vykonaním automatického pohybu.",
    "drive_random": "Pridá náhodné čakanie od nuly po túto hodnotu k pevnému oneskoreniu.",
    "debug": "Ukladá aj podrobné vyhodnotenia podmienok. Zväčšuje množstvo záznamov.",
    "logbook": "Zapisuje významné udalosti automatizácie aj do záznamníka Home Assistanta.",
    "logbook_cover": "Záznamy v záznamníku priradí k ovládanej žalúzii.",
    "retention_days": "Staršie udalosti sa odstránia po tomto počte dní; platí aj maximálny počet záznamov.",
    "history_limit": "Horný limit uložených udalostí jednej automatizácie. Po naplnení sa najstaršie odstránia.",
}


def _field_help(key: str, field: Field) -> str:
    if key in _HELP:
        return _HELP[key]
    if field.help:
        return field.help.replace(
            "všetky AND a aspoň jedna OR",
            "podmienky prvej skupiny a aspoň jedna podmienka druhej skupiny",
        )
    if field.kind == "condition":
        return "Tieto podmienky musia platiť pred príslušným automatickým pohybom. Prázdny zoznam nepridáva ďalšie obmedzenie."
    if field.kind == "action":
        return "Vybrané akcie Home Assistanta sa vykonajú pri uvedenej udalosti. Prázdny zoznam nevykoná žiadne doplnkové akcie."
    if field.kind == "entity":
        return f"Vyber zdroj pre nastavenie „{field.label}“. Prázdny výber tento voliteľný zdroj nepoužije."
    if field.kind == "time":
        edge = "najneskorší" if "late" in key else "najskorší"
        action = "otvorenia" if key.startswith("morning") else "zatvorenia"
        return f"Určuje {edge} čas {action} pre uvedený typ dňa. Skutočný pohyb závisí aj od zapnutých podmienok a ochrán."
    if key.endswith("_position"):
        return f"Cieľová poloha pre nastavenie „{field.label}“. Percentá sa riadia polohou zariadenia a zvoleným typom žalúzie."
    if "hysteresis" in key:
        return "Rezerva pri návrate cez hranicu zabraňuje opakovanému prepínaniu podmienky pri malých výkyvoch hodnoty."
    if field.kind == "bool":
        return f"Zapne pravidlo „{field.label}“ pre túto žalúziu. Po vypnutí sa toto pravidlo neuplatní."
    if field.kind == "multi":
        return f"Vyber možnosti pre pravidlo „{field.label}“. Použijú sa iba označené položky."
    if field.unit == "s":
        return f"Doba pre nastavenie „{field.label}“. Vyššia hodnota predĺži čakanie."
    if field.unit == "°C":
        return f"Teplotná hranica pre nastavenie „{field.label}“ v stupňoch Celzia. Použije sa pri vyhodnocovaní vybranej podmienky."
    if field.unit == "°":
        return f"Hranica pre nastavenie „{field.label}“ v stupňoch. Použije sa pri vyhodnocovaní polohy slnka."
    return f"Určuje hodnotu nastavenia „{field.label}“ pre túto automatizáciu."


for _key, _field in FIELDS.items():
    _field = replace(_field, label=_LABELS.get(_key, _field.label))
    FIELDS[_key] = replace(_field, help=_field_help(_key, _field))


class ConfigError(ValueError):
    """Configuration cannot be safely applied."""

    def __init__(self, key: str, message: str):
        self.key = key
        super().__init__(f"{FIELDS[key].label if key in FIELDS else key}: {message}")


def validate_config(raw: dict, *, cover_entity: str | None = None) -> dict:
    """Validate untrusted data and return an independent normalized configuration."""
    if not isinstance(raw, dict):
        raise ConfigError("config", "očakáva sa objekt")
    raw = deepcopy(raw)
    if raw.get("lux_sensor") and not raw.get("shade_lux_sensor"):
        raw["shade_lux_sensor"] = raw["lux_sensor"]
    unknown = set(raw) - FIELDS.keys() - LEGACY_CONFIG_FIELDS - {"position_source_auto"}
    if unknown:
        raise ConfigError(sorted(unknown)[0], "neznáme nastavenie")
    raw = {key: value for key, value in raw.items() if key not in LEGACY_CONFIG_FIELDS}
    cfg = {key: deepcopy(raw.get(key, spec.default)) for key, spec in FIELDS.items()}
    auto_source = (
        raw["position_source_auto"]
        if "position_source_auto" in raw
        else raw.get("position_source", "current_position") == "current_position"
    )
    if type(auto_source) is not bool:
        raise ConfigError("position_source", "automatický výber musí byť prepínač")
    cfg["position_source_auto"] = auto_source
    if cfg["cover_type"] in ("awning", "sunshade"):
        for key, value in (("open_position", 0), ("close_position", 100), ("lockout_position", 0)):
            if key not in raw:
                cfg[key] = value
        if cfg["ventilation_enabled"]:
            raise ConfigError("ventilation_enabled", "vetranie nie je dostupné pre markízu")
    for key, spec in FIELDS.items():
        value = cfg[key]
        if spec.kind == "bool" and type(value) is not bool:
            raise ConfigError(key, "očakáva sa prepínač")
        if spec.kind == "number":
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not spec.minimum <= value <= spec.maximum
            ):
                raise ConfigError(key, f"rozsah {spec.minimum} až {spec.maximum}")
        elif spec.kind in ("entity", "text", "time", "select"):
            if not isinstance(value, str):
                raise ConfigError(key, "očakáva sa text")
            if spec.kind == "entity" and value and not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", value):
                raise ConfigError(key, "neplatná entita")
            if spec.kind == "time" and not re.fullmatch(
                r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", value
            ):
                raise ConfigError(key, "neplatný čas")
            if spec.kind == "select" and value not in spec.options:
                raise ConfigError(key, "neplatná možnosť")
        elif spec.kind == "multi":
            if not isinstance(value, list) or any(x not in spec.options for x in value):
                raise ConfigError(key, "neplatný výber")
        elif spec.kind in ("action", "condition"):
            if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
                raise ConfigError(key, "očakáva sa zoznam podmienok alebo akcií")
    if not cfg["cover_entity"].startswith("cover."):
        raise ConfigError("cover_entity", "vyber entitu cover")
    if cover_entity is not None and cfg["cover_entity"] != cover_entity:
        raise ConfigError("cover_entity", "identitu existujúcej žalúzie nemožno zmeniť")
    if not cfg["name"].strip():
        raise ConfigError("name", "názov je povinný")
    cfg["name"] = cfg["name"].strip()
    if cfg["open_position"] == cfg["close_position"]:
        raise ConfigError("close_position", "otvorená a zatvorená poloha musia byť rôzne")
    for prefix in ("morning", "evening"):
        for suffix in ("", "_free"):

            def seconds(value):
                parts = [int(x) for x in value.split(":")]
                return parts[0] * 3600 + parts[1] * 60 + (parts[2] if len(parts) > 2 else 0)

            if seconds(cfg[f"{prefix}_early{suffix}"]) > seconds(cfg[f"{prefix}_late{suffix}"]):
                raise ConfigError(f"{prefix}_early{suffix}", "najskorší čas je po najneskoršom")
    if cfg["shade_elevation_min"] > cfg["shade_elevation_max"]:
        raise ConfigError("shade_elevation_min", "dolná hranica je väčšia ako horná")
    if cfg["position_source"] == "sensor" and not cfg["position_sensor"]:
        raise ConfigError("position_sensor", "vyber senzor polohy")
    return cfg
