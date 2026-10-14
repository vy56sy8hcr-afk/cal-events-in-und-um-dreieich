#!/usr/bin/env python3
"""Baut cal-events-in-und-um-dreieich.ics aus Rhythmus-Regeln (dieses Skript)
und bestaetigten Terminen (termine.json). Bestaetigte Termine haben Vorrang.
Fenster: heute -6 Monate bis +16 Monate."""
import hashlib, json, os, re, sys, uuid
from datetime import date, timedelta

AUSGABE = "cal-events-in-und-um-dreieich.ics"
PFEIL_TAGE = int(os.environ.get("PFEIL_TAGE", "3"))   # Pfeil-Termine ueber 3 Tage
WD = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
D = date

def heute():
    a = os.environ.get("HEUTE")
    return D.fromisoformat(a) if a else date.today()

def add_months(d, m):
    y, mo = divmod(d.year * 12 + d.month - 1 + m, 12)
    mo += 1
    tag = d.day
    while True:
        try:
            return D(y, mo, tag)
        except ValueError:
            tag -= 1

def easter(y):
    a = y % 19; b = y // 100; c = y % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31; da = (h + l - 7 * m + 114) % 31 + 1
    return D(y, mo, da)

def nth(y, m, wd, n):
    d = D(y, m, 1)
    while d.weekday() != wd: d += timedelta(1)
    return d + timedelta(7 * (n - 1))

def zwischen(y, m, wd, d1, d2):
    """Datum mit Wochentag wd zwischen d1 und d2 (einschliesslich) im Monat m."""
    for t in range(d1, d2 + 1):
        if D(y, m, t).weekday() == wd: return D(y, m, t)

def letzter(y, m, wd):
    d = D(y, m + 1, 1) - timedelta(1) if m < 12 else D(y, 12, 31)
    while d.weekday() != wd: d -= timedelta(1)
    return d

def advent1(y):
    d = D(y, 12, 25) - timedelta((D(y, 12, 25).weekday() + 1) % 7 or 7)  # 4. Advent
    return d - timedelta(21)

def nach_so(d):
    d += timedelta(1)
    while d.weekday() != 6: d += timedelta(1)
    return d

def zo(x): return x.replace("0", "o")   # Null immer als kleines o
def f(d): return f"{WD[d.weekday()]} {d:%d.%m.%Y}"

WM_BLOCK = (
    "WEIHNACHTSMÄRKTE IN DREIEICH\n\n"
    "1. Advent Adventsmarkt Sprendlingen Lindenplatz, Sprendlingen\n"
    "Freitag von 17-21 Uhr\nSamstag und Sonntag von 15-21 Uhr\n"
    "seit 2000. In 2025 wurden 25 Jahre gefeiert.\nVeranstalter: AKTIVes Dreieich e.V.\n\n"
    "2. und 3. Advent: Hayner Weihnachtsmarkt Dreieichenhain, Fahrgasse\n"
    "Freitag je von 17-21:30 Uhr\nSamstag und Sonntag je von 15-21:30 Uhr\n"
    "Veranstalter: Gewerbeverein Dreieich e. V. und Werbegemeinschaft Dreieichenhain e.V.\n"
    "Seit 1978. In 2027 werden 50 Jahre gefeiert.\n\n"
    "4. Advent: Weihnachtsmarkt Offenthal\n"
    "Kirchgasse, Kirchgarten, Altes Rathaus\n"
    "Samstag von 16-22 Uhr\nSonntag von 14-20 Uhr\n"
    "bzw. wenn Weihnachten auf Sonntag fällt, dann\nFreitag von 16-22 Uhr\nSamstag von 14-20 Uhr\n"
    "Veranstalter: Kulturverein Dreieich e.V."
)

ITEMS = {}   # key -> dict(start, ende, titel, notiz)

def einzel(key, titel, start, ende=None, notiz=""):
    ITEMS[key] = dict(start=start, ende=ende or start, titel=titel, notiz=notiz)

def rng(s, e): return f"({zo(f'{s:%d.%m.}')} - {zo(f'{e.day:02d}.{e.month}.{e.year}')})"

def pfeil(key, emoji, name, s, e, notiz="", wort=False, pre="▼ "):
    r = rng(s, e); n = PFEIL_TAGE - 1
    t1 = f"{pre}—>{emoji}{name} " + ("Eröffnung " if wort else "") + r
    t2 = f"{pre}<—{emoji}{name} " + ("Ende " if wort else "") + r
    ITEMS[key + "#anfang"] = dict(start=s, ende=s + timedelta(n), titel=t1, notiz=notiz)
    ITEMS[key + "#ende"] = dict(start=e - timedelta(n), ende=e, titel=t2, notiz=notiz)

# Termine, die sich aus gefunden.json selbst anlegen (auch fuer neue Jahre).
# Schluessel = Name der Vorlage. art: pfeil (ueber 7 Tage) oder einzel.
# n0 = Zaehlung im Jahr j0 (zaehlt pro Jahr um 1 hoch), {n} {s} {e} im Text = Zaehlung, Start, Ende.
VORLAGEN = {
    "kunsttage-fruehjahr": dict(art="pfeil", emoji="🎨", name="{n}. Kunsttage Dreieich", n0=35, j0=2027,
                                notiz="www.buergerhaeuser-dreieich.de/kunsttage/aktuelles"),
    "kunsttage-burg": dict(art="pfeil", emoji="🎨", name="{n}. Kunsttage Dreieich Kunst in der Burg", n0=35, j0=2027,
                           notiz="www.buergerhaeuser-dreieich.de/kunsttage/aktuelles"),
    "kunsttage-herbst": dict(art="pfeil", emoji="🎨", name="{n}. Kunsttage Dreieich", n0=35, j0=2027,
                             notiz="www.buergerhaeuser-dreieich.de/kunsttage/aktuelles"),
    "musiktage": dict(art="pfeil", emoji="🎼", name="{n}. Dreieicher Musiktage", n0=25, j0=2027,
                      notiz="{n}. Dreieicher Musiktage\nVeranstalter: Bürgerhäuser Dreieich"),
    "burgfestspiele": dict(art="pfeil", emoji="🌀", name="Burgfestspiele Dreieichenhain", wort=True,
                           notiz="Burgfestspiele Dreieichenhain\n{s:%d.%m.%Y} – {e:%d.%m.%Y}"),
    "festspiele-hanau": dict(art="pfeil", emoji="🎭", name="Brüder Grimm Festspiele Hanau", wort=True, pre="", n0=43, j0=2027,
                             notiz="Brüder Grimm Festspiele Hanau\n{n}. Spielzeit, {s:%d.%m.%Y} – {e:%d.%m.%Y}"),
    "weihnachtsmarkt-darmstadt": dict(art="pfeil", emoji="🎅🏼", name="Darmstädter Weihnachtsmarkt", pre="",
                                      notiz="Darmstädter Weihnachtsmarkt\nwww.darmstadt-guide.de/veranstaltungen/"),
    "adventsmarkt-seligenstadt": dict(art="pfeil", emoji="🎅", name="Adventsmarkt Seligenstadt", pre="",
                                      notiz="Adventsmarkt Seligenstadt\nwww.deutsche-fachwerkstrasse.de/Themen/Weihnachtsmaerkte.html"),
    "weihnachtsmarkt-hoechst": dict(art="einzel", titel="🎅🏼Höchster Weihnachtsmarkt Frankfurt-Höchst",
                                    notiz="Höchster Weihnachtsmarkt Frankfurt-Höchst\nwww.deutsche-fachwerkstrasse.de/Themen/Weihnachtsmaerkte.html"),
    "tauschboerse": dict(art="einzel", titel="🌿Tausch- und Verschenkbörse",
                         notiz="Tausch- und Verschenkbörse\nwww.klimaenergie-frm.de/Streuobst/Streuobst-Portal/Aktionskalender/"),
    "gluehaepplerfest": dict(art="einzel", titel="🌿GlühÄpplerFest",
                             notiz="GlühÄpplerFest\nwww.klimaenergie-frm.de/Streuobst/Streuobst-Portal/Aktionskalender/"),
}

def regeln(y):
    ostern = easter(y)
    pfingsten = ostern + timedelta(49)
    fronleichnam = ostern + timedelta(60)
    # --- Dreieich: Kerben ---
    hain = (pfingsten - timedelta(2), pfingsten + timedelta(3))
    gs = nth(y, 9, 6, 3)
    goet = (gs - timedelta(2), gs + timedelta(1))
    a10 = D(y, 8, 10)
    sa = a10 - timedelta(1) if a10.weekday() == 6 else a10 + timedelta((5 - a10.weekday()) % 7)
    spr = (sa - timedelta(1), sa + timedelta(3))
    os_ = nach_so(D(y, 10, 28))
    off = (os_ - timedelta(2), os_ + timedelta(2))
    note = (f"Die Kerben und ihre Termine {y} in Dreieich:\n\nHayner Kerb (Dreieichenhain)\n{f(hain[0])} – {f(hain[1])}\n\n"
            f"Kerb Sprendlingen\n{f(spr[0])} – {f(spr[1])}\n\nKerb Götzenhain\n{f(goet[0])} – {f(goet[1])}\n\n"
            f"Kerb Offenthal\n{f(off[0])} – {f(off[1])}")
    k = y - 2026
    einzel(f"haaner-kerb-{y}", f"▼ 🎈{308 + k}. Haaner Kerb", *hain, notiz=note)
    einzel(f"sprendlinger-kerb-{y}", f"▼ 🎈{310 + k}. Sprendlinger Kerb", *spr, notiz=note)
    einzel(f"goetzenhainer-kerb-{y}", f"▼ 🎈{250 + k}. Götzenhainer Kerb", *goet, notiz=note)
    einzel(f"offenthaler-kerb-{y}", "▼ 🎈Offenthaler Kerb", *off, notiz=note)
    einzel(f"kerb-warmup-{y}", "▼ 🎈Kerb-Warmup Lindenplatz", spr[0] - timedelta(13), notiz="Kerb-Warmup Lindenplatz")
    # --- Dreieich: weitere ---
    wf = fronleichnam - timedelta(1)
    einzel(f"weinfest-buergerpark-{y}", "▼ 🍷Weinfest Bürgerpark Sprendlingen", wf, wf + timedelta(4),
           "Weinfest im Bürgerpark Sprendlingen\nVeranstalter: AKTIVes Dreieich e.V.\nbeginnt immer 1 Tag vor Fronleichnam")
    j = nth(y, 6, 5, 3)
    einzel(f"offene-gaerten-{y}", "▼ 🌿Offene Gärten Buchschlag", j, j + timedelta(1))
    b = zwischen(y, 9, 4, 6, 12)
    einzel(f"hayner-burgfest-{y}", "▼ 🏰Hayner Burgfest", b, b + timedelta(2))
    einzel(f"hayner-toepfermarkt-{y}", "▼ 🎨Hayner Töpfermarkt", letzter(y, 9, 6))
    einzel(f"stadtfest-{y}", "▼🎈🛍️Stadtfest VoF", D(y, 10, 3))
    bs = zwischen(y, 6, 2, 23, 29)    # Burgfestspiele (Rhythmus als Reserve, 2 Stichproben)
    pfeil(f"burgfestspiele-{y}", "🌀", "Burgfestspiele Dreieichenhain", bs, bs + timedelta(46), wort=True,
          notiz=f"Burgfestspiele Dreieichenhain\n{bs:%d.%m.%Y} – {(bs + timedelta(46)):%d.%m.%Y}")
    # Weihnachtsmaerkte Dreieich
    a1 = advent1(y)
    ad = ("Adventsmarkt Sprendlingen\nLindenplatz, Sprendlingen\nFr 17–21 Uhr, Sa und So 15–21 Uhr\n"
          "seit 2000 (2025: 25 Jahre)\nVeranstalter: AKTIVes Dreieich e.V.")
    hn = "Hayner Weihnachtsmarkt\nDreieichenhain, Fahrgasse\nFr 17–21:30 Uhr, Sa und So 15–21:30 Uhr\nseit 1978 (2027: 50 Jahre)"
    of = ("Weihnachtsmarkt Offenthal\nKirchgasse, im Kirchgarten und am Alten Rathaus\nSa 16–22 Uhr, So 14–20 Uhr "
          "(fällt Weihnachten auf einen Sonntag: Fr 16–22 Uhr, Sa 14–20 Uhr)\nVeranstalter: Kulturverein Dreieich e.V.")
    ad = hn = of = WM_BLOCK
    einzel(f"adventsmarkt-sprendlingen-{y}", "▼ 🎅Adventsmarkt Sprendlingen, Lindenplatz (1. Advent)", a1 - timedelta(2), a1, ad)
    einzel(f"hayner-wm-2-{y}", "▼ 🎅Hayner Weihnachtsmarkt, Dreieichenhain (2. Advent
