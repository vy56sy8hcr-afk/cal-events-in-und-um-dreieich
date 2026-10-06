#!/usr/bin/env python3
"""Baut cal-events-in-und-um-dreieich.ics aus Rhythmus-Regeln (dieses Skript)
und bestaetigten Terminen (termine.json). Bestaetigte Termine haben Vorrang.
Fenster: heute -6 Monate bis +16 Monate."""
import json, os, sys, uuid
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

ITEMS = {}   # key -> dict(start, ende, titel, notiz)

def einzel(key, titel, start, ende=None, notiz=""):
    ITEMS[key] = dict(start=start, ende=ende or start, titel=titel, notiz=notiz)

def rng(s, e): return f"({zo(f'{s:%d.%m.}')} - {zo(f'{e.day:02d}.{e.month}.{e.year}')})"

def pfeil(key, emoji, name, s, e, notiz="", wort=False):
    r = rng(s, e); n = PFEIL_TAGE - 1
    t1 = f"▼ —>{emoji}{name} " + ("Eröffnung " if wort else "") + r
    t2 = f"▼ <—{emoji}{name} " + ("Ende " if wort else "") + r
    ITEMS[key + "#anfang"] = dict(start=s, ende=s + timedelta(n), titel=t1, notiz=notiz)
    ITEMS[key + "#ende"] = dict(start=e - timedelta(n), ende=e, titel=t2, notiz=notiz)

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
           "Weinfest im Bürgerpark Sprendlingen\nVeranstalter: AKTIVes Dreieich e.V.")
    j = nth(y, 6, 5, 3)
    einzel(f"offene-gaerten-{y}", "▼ 🌿Offene Gärten Buchschlag", j, j + timedelta(1))
    b = zwischen(y, 9, 4, 6, 12)
    einzel(f"hayner-burgfest-{y}", "▼ 🏰Hayner Burgfest", b, b + timedelta(2))
    einzel(f"hayner-toepfermarkt-{y}", "▼ 🎨Hayner Töpfermarkt", letzter(y, 9, 6))
    einzel(f"stadtfest-{y}", "▼ 🎈Stadtfest", D(y, 10, 3))
    bs = zwischen(y, 6, 2, 23, 29)    # Burgfestspiele (Rhythmus als Reserve, 2 Stichproben)
    pfeil(f"burgfestspiele-{y}", "🌀", "Burgfestspiele Dreieichenhain", bs, bs + timedelta(46), wort=True,
          notiz=f"Burgfestspiele Dreieichenhain\n{bs:%d.%m.%Y} – {(bs + timedelta(46)):%d.%m.%Y}")
    # Weihnachtsmaerkte Dreieich
    a1 = advent1(y)
    ad = ("Adventsmarkt Sprendlingen\nLindenplatz, Sprendlingen\nFr 17–21 Uhr, Sa und So 15–21 Uhr\n"
          "seit 2000 (2025: 25 Jahre)\nVeranstalter: AKTIVes Dreieich e.V.")
    hn = "Hayner Weihnachtsmarkt\nDreieichenhain, Fahrgasse\nSa 15–20:30 Uhr, So 14–20 Uhr\nseit 1978 (2027: 50 Jahre)"
    of = ("Weihnachtsmarkt Offenthal\nKirchgasse, im Kirchgarten und am Alten Rathaus\nSa 16–22 Uhr, So 14–20 Uhr "
          "(fällt Weihnachten auf einen Sonntag: Fr 16–22 Uhr, Sa 14–20 Uhr)\nVeranstalter: Kulturverein Dreieich e.V.")
    einzel(f"adventsmarkt-sprendlingen-{y}", "▼ 🎅🏼Adventsmarkt Sprendlingen, Lindenplatz (1. Advent)", a1 - timedelta(2), a1, ad)
    einzel(f"hayner-wm-2-{y}", "▼ 🎅🏼Hayner Weihnachtsmarkt, Dreieichenhain (2. Advent)", a1 + timedelta(6), a1 + timedelta(7), hn)
    einzel(f"hayner-wm-3-{y}", "▼ 🎅🏼Hayner Weihnachtsmarkt, Dreieichenhain (3. Advent)", a1 + timedelta(13), a1 + timedelta(14), hn)
    if D(y, 12, 25).weekday() == 6:
        einzel(f"offenthal-wm-{y}", "▼ 🎅🏼Weihnachtsmarkt Offenthal (4. Advent)", D(y, 12, 23), D(y, 12, 24), of)
    else:
        einzel(f"offenthal-wm-{y}", "▼ 🎅🏼Weihnachtsmarkt Offenthal (4. Advent)", a1 + timedelta(20), a1 + timedelta(21), of)
    # --- Langen ---
    himmel = ostern + timedelta(39)
    einzel(f"countryfest-langen-{y}", "🎈Countryfest Langen", himmel, himmel + timedelta(1))
    e = nth(y, 6, 4, 3)
    einzel(f"ebbelwoifest-{y}", "🎈Ebbelwoifest Langen", e, e + timedelta(3))
    w = zwischen(y, 8, 3, 6, 12)
    einzel(f"weinfest-langen-{y}", "🍷Weinfest Langen", w, w + timedelta(3))
    so1 = nth(y, 9, 6, 1)
    einzel(f"langener-kerb-{y}", "🎈Langener Kerb", so1 - timedelta(1), so1 + timedelta(2))
    einzel(f"langener-markt-{y}", "🛍️Langener Markt", so1)
    einzel(f"art-promenade-{y}", "🎨Art Promenade Langen", so1)
    gf = nth(y, 9, 4, 3)
    einzel(f"gartenfest-langen-{y}", "🌿Fürstliches Gartenfest Langen", gf, gf + timedelta(2))
    einzel(f"wm-langen-1-{y}", "🎅🏼Weihnachtsmarkt Langen", a1 - timedelta(2), a1)
    einzel(f"wm-langen-2-{y}", "🎅🏼Weihnachtsmarkt Langen", a1 + timedelta(5), a1 + timedelta(7))
    # --- Neu-Isenburg ---
    o = nth(y, 7, 4, 2)
    einzel(f"opendoors-ni-{y}", "🎵OpenDoors N-I", o, o + timedelta(2))
    wn = zwischen(y, 8, 4, 7, 13)
    einzel(f"weinfest-ni-{y}", "🍷Weinfest N-I", wn, wn + timedelta(9))
    einzel(f"wm-ni-{y}", "🎅🏼Weihnachtsmarkt N-I", a1 + timedelta(6), a1 + timedelta(7))
    rm = ostern - timedelta(48)
    einzel(f"rathaussturm-ni-{y}", "🎈Rathaussturm N-I", rm - timedelta(9))
    einzel(f"lumpenmontag-ni-{y}", "🎈Lumpenmontagsumzug N-I", rm)
    # --- Umland ---
    einzel(f"schlossgrabenfest-{y}", "🎈Schlossgrabenfest Darmstadt", pfingsten - timedelta(3), pfingsten + timedelta(1))
    sa1 = nth(y, 7, 5, 1)
    einzel(f"heinerfest-{y}", "🎈🎵Heinerfest Darmstadt", sa1 - timedelta(2), sa1 + timedelta(2))
    einzel(f"rembruecker-{y}", "🍷Rembrücker Weintage", o, o + timedelta(2))
    einzel(f"weinwoche-rodgau-{y}", "🍷Weinwoche Rodgau", o, o + timedelta(9))
    d4 = nth(y, 7, 4, 4)
    einzel(f"weinfest-dietzenbach-{y}", "🍷Weinfest Dietzenbach", d4, d4 + timedelta(9))
    h3 = nth(y, 8, 2, 3)
    einzel(f"weinfest-heusenstamm-{y}", "🍷Weinfest Heusenstamm", h3, h3 + timedelta(5))

def lade_bestaetigt(pfad="termine.json"):
    if not os.path.exists(pfad): return
    daten = json.load(open(pfad, encoding="utf-8"))
    for t in daten.get("termine", []):
        key = t["key"]
        if t.get("skip"):
            for k in [k for k in ITEMS if k == key or k.startswith(key + "#")]: del ITEMS[k]
            continue
        s = D.fromisoformat(t["start"]); e = D.fromisoformat(t.get("ende", t["start"]))
        typ = t.get("typ", "einzel")
        for k in [k for k in ITEMS if k == key or k.startswith(key + "#")]: del ITEMS[k]
        if typ == "einzel":
            einzel(key, t["titel"], s, e, t.get("notiz", ""))
        else:
            pfeil(key, t["emoji"], t["name"], s, e, t.get("notiz", ""), wort=(typ == "pfeil_wort"))

def esc(s): return s.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def falten(zeile):
    b = zeile.encode("utf-8"); out = []
    while len(b) > 74:
        c = 74
        while (b[c] & 0xC0) == 0x80: c -= 1
        out.append(b[:c].decode("utf-8")); b = b" " + b[c:]
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)

def main():
    h = heute()
    von, bis = add_months(h, -6), add_months(h, 16)
    for y in range(von.year, bis.year + 1): regeln(y)
    lade_bestaetigt()
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Veranstaltungen Dreieich Langen N-I//DE", "CALSCALE:GREGORIAN",
         "X-WR-CALNAME:Veranstaltungen Dreieich Langen N-I", "X-WR-TIMEZONE:Europe/Berlin",
         "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    n = 0
    for key, it in sorted(ITEMS.items(), key=lambda kv: (kv[1]["start"], kv[1]["titel"])):
        if not (von <= it["start"] <= bis): continue
        n += 1
        uid = uuid.uuid5(uuid.NAMESPACE_URL, "events-dreieich|" + key)
        L += ["BEGIN:VEVENT", f"UID:{uid}@events-dreieich", "DTSTAMP:20260101T000000Z",
              f"DTSTART;VALUE=DATE:{it['start']:%Y%m%d}", f"DTEND;VALUE=DATE:{(it['ende'] + timedelta(1)):%Y%m%d}",
              falten("SUMMARY:" + esc(it["titel"]))]
        if it["notiz"]: L.append(falten("DESCRIPTION:" + esc(it["notiz"])))
        L.append("END:VEVENT")
    L.append("END:VCALENDAR")
    with open(AUSGABE, "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(L) + "\r\n")
    print(f"{n} Termine, Fenster {von} bis {bis}")

if __name__ == "__main__":
    main()
