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
    "1. Advent Adventsmarkt Sprendlingen Lindenplatz, Sprendlingen, beginnend am Freitag\n"
    "Freitag von 17-21 Uhr\nSamstag und Sonntag von 15-21 Uhr\n"
    "seit 2000. In 2025 wurden 25 Jahre gefeiert.\nVeranstalter: AKTIVes Dreieich e.V.\n\n"
    "2. und 3. Advent: Hayner Weihnachtsmarkt Dreieichenhain, Fahrgasse\n"
    "Samstag je von 15-20:30 Uhr\nSonntag je von 14-20 Uhr\n"
    "Seit 1978. In 2027 werden 50 Jahre gefeiert.\n\n"
    "4. Advent: Weihnachtsmarkt Offenthal\n"
    "Kirchgasse, im Kirchgarten und am Alten Rathaus\n"
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
                           notiz="www.buergerhaeuser-dreieich.de/kunsttage/akt
