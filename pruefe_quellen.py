#!/usr/bin/env python3
"""Liest taeglich die Quellen aus quellen.json.
- "datum": liest Termine mit festem Satz -> gefunden.json (Kalender legt sie selbst an oder korrigiert sie)
- "beobachten"/"grossstaedte":
  * Advents-/Weihnachts-/Nikolausmaerkte aus Kalenderseiten im Kreis Offenbach -> gefunden.json ("auto"),
    der Kalender nimmt sie selbst auf (nur bei eindeutigem Datum mit Jahr, nur wenn neu)
  * alles andere: NEUE Treffer als fertige Zeilen fuer eigene_termine.txt in vorschlaege.txt
    (alte bleiben stehen; Bekanntes und Begriffe aus ablehnungen.txt kommen nicht hinein)
Faellt eine Seite aus, passiert nichts: der Kalender bleibt unveraendert.
Protokoll: quellen-log.txt (bei Abbruch steht dort ABGEBROCHEN mit der Fehlermeldung)"""
import html as htmllib, json, os, re, time, traceback, urllib.parse, urllib.request, uuid
from datetime import date, timedelta

MONATE = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
          "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}
MON = r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
BIS = r"(?:bis(?:\s+zum)?|[-–+]|und)"
MUSTER = [
    ("B", re.compile(r"(\d{1,2})\.\s*" + MON + r"\s*(?:bis(?:\s+zum)?|[-–])\s*(\d{1,2})\.\s*" + MON + r"(?:\s+(\d{4}))?", re.I)),
    ("A", re.compile(r"(\d{1,2})\.\s*" + BIS + r"\s*(\d{1,2})\.\s*" + MON + r"(?:\s+(\d{4}))?", re.I)),
    ("D", re.compile(r"(\d{1,2})\.(?:(\d{1,2})\.)?\s*" + BIS + r"\s*(\d{1,2})\.(\d{1,2})\.(?:\s*(\d{4}))?", re.I)),
    ("C", re.compile(r"(\d{1,2})\.\s*" + MON + r"(?:\s+(\d{4}))?", re.I)),
    ("E", re.compile(r"(\d{1,2})\.(\d{1,2})\.\s?(\d{4})")),
]
LOG = []
LAHM = set()   # Server, die nicht antworten: weitere Seiten werden uebersprungen
RAUSCHEN = re.compile(r"Verkehrsbehinderung|Verkehrsinfo|Straßensperr|Sperrung|Bekanntmachung", re.I)
AUSGABE = "cal-events-in-und-um-dreieich.ics"
UID_PREFIX = "events-dreieich-v2|"   # muss zu build_ics.py passen
STADT_NAME = {"neu-isenburg": "N-I", "dreieich": "", "bad-homburg": "Bad Homburg", "fachwerkstrasse": "",
              "apfelweinroute": "", "roedermark": "Rödermark", "muehlheim": "Mühlheim"}
STADT_TOKEN = {"dreieich": ["▼"], "neu-isenburg": ["n-i", "isenburg"], "bad-homburg": ["homburg"],
               "heusenstamm": ["heusen", "rembr"], "fachwerkstrasse": [], "apfelweinroute": []}
AUTO_STAEDTE = ["dietzenbach", "neu-isenburg", "rodgau", "dreieich", "langen", "muehlheim", "egelsbach", "heusenstamm",
                "hainburg", "mainhausen", "obertshausen", "roedermark", "seligenstadt"]
AUTO_WOERTER = ["Weihnachtsmarkt", "Adventsmarkt", "Nikolausmarkt", "Winterzauber"]
AUTO_ARTEN = ["Kalender"]
OHNE_VORSCHLAEGE = ["fachwerkstrasse", "apfelweinroute", "darmstadt"]
KOPF = ("# Vorschlaege, Stand {heute}. Neue Treffer werden unten angefuegt, alte bleiben stehen.\n"
        "# Zeile mit #> = Hinweis zur Quelle. Die Zeile darunter kopierst du in eigene_termine.txt (Titel und Emoji anpassen).\n"
        "# Nicht gewollt? Begriff in ablehnungen.txt eintragen. Was im Kalender, in termine.json oder eigene_termine.txt steht, verschwindet von selbst.\n\n")
ABL_START = ("# Ablehnungen: ein Begriff pro Zeile (Gross/Klein egal). Passt der Begriff zu einem Treffer, kommt er nicht in vorschlaege.txt.\n"
             "lagerhof\nflohmarkt\ngrünberg\nwolfhagen\nmelsungen\n")

def log(zeile): LOG.append(zeile); print(zeile)

def hole(url):
    """Bis zu 3 Versuche, 45 Sekunden Wartezeit je Versuch."""
    letzter = None
    for versuch in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept-Language": "de-DE,de;q=0.9"})
            with urllib.request.urlopen(req, timeout=45) as r:
                roh = r.read(); cs = r.headers.get_content_charset() or "utf-8"
            return roh.decode(cs, errors="replace")
        except Exception as ex:
            letzter = ex
            if "404" in str(ex): break          # Seite gibt es nicht, nicht wiederholen
            time.sleep(5)
    raise letzter

def als_text(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    t = htmllib.unescape(re.sub(r"(?s)<[^>]+>", " ", h)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t)

def monat(name): return MONATE.get(name.lower())

def finde(quelle, text):
    """Gibt Liste (key, start, ende, vorlage) zurueck."""
    out = []
    for m in re.finditer(quelle["muster"], text, re.I):
        g = m.groups(); typ = quelle["typ"]
        try:
            if typ == "einzeltag":                  # 28. August 2026
                t, mo, j = int(g[0]), monat(g[1]), int(g[2]); s = e = date(j, mo, t)
            elif typ == "zeitraum":                 # 28. - 30. August 2026
                t1, t2, mo, j = int(g[0]), int(g[1]), monat(g[2]), int(g[3])
                s, e = date(j, mo, t1), date(j, mo, t2)
            elif typ == "zeitraum_num":             # 27.08. bis 30.08.2027
                d1, m1, d2, m2, j = (int(x) for x in g[:5])
                s, e = date(j, m1, d1), date(j, m2, d2)
            elif typ == "zeitraum_mon":             # 29. April bis 17. Mai 2027
                t1, m1, t2, m2, j = int(g[0]), monat(g[1]), int(g[2]), monat(g[3]), int(g[4])
                s, e = date(j, m1, t1), date(j, m2, t2)
            elif typ == "zeitraum_voll":            # 28.11.2026 - 29.11.2026
                d1, m1, y1, d2, m2, y2 = (int(x) for x in g[:6])
                s, e = date(y1, m1, d1), date(y2, m2, d2)
            elif typ == "tage_num":                 # 12. und 13.12.2026  /  02. - 06.07.2026
                d1, d2, mo, j = (int(x) for x in g[:4])
                s, e = date(j, mo, d1), date(j, mo, d2)
            else:
                continue
        except (TypeError, ValueError):
            continue
        heute = date.today()
        if not (heute - timedelta(400) <= s <= heute + timedelta(700)) or e < s: continue
        out.append((quelle["key"].format(jahr=s.year, datum=s.isoformat()), s, e, quelle.get("vorlage")))
    return out

def sauber(text, a, b):
    """Ausschnitt text[a:b] ohne abgeschnittene Woerter am Rand."""
    a = max(0, a); b = min(len(text), b)
    if a > 0 and not text[a - 1].isspace():
        k = text.find(" ", a)
        if 0 <= k < b: a = k + 1
    if b < len(text) and not text[b].isspace():
        k = text.rfind(" ", a, b)
        if k > a: b = k
    return text[a:b].strip()

def datum_treffer(txt, heute, streng=False):
    """Alle Datumsangaben im Text: Liste (pos_von, pos_bis, start, ende).
    streng: nur mit ausdruecklicher Jahreszahl (Zahlendatum nur mit Uhrzeit dahinter)."""
    wj = re.search(r"\b(20\d\d)\b", txt)
    wj = int(wj.group(1)) if wj else None
    belegt, out = [], []
    for art, mu in MUSTER:
        for m in mu.finditer(txt):
            a, b = m.span()
            if any(a < y and x < b for x, y in belegt): continue
            g = m.groups()
            jahr_da = g[{"A": 3, "B": 4, "D": 4, "C": 2, "E": 2}[art]]
            if streng and not jahr_da: continue
            try:
                if art == "A":
                    y = int(g[3]) if g[3] else (wj or heute.year); mo = monat(g[2])
                    s, e = date(y, mo, int(g[0])), date(y, mo, int(g[1]))
                elif art == "B":
                    y = int(g[4]) if g[4] else (wj or heute.year)
                    s, e = date(y, monat(g[1]), int(g[0])), date(y, monat(g[3]), int(g[2]))
                elif art == "D":
                    y = int(g[4]) if g[4] else (wj or heute.year); m2 = int(g[3]); m1 = int(g[1]) if g[1] else m2
                    s, e = date(y, m1, int(g[0])), date(y, m2, int(g[2]))
                elif art == "C":
                    y = int(g[2]) if g[2] else (wj or heute.year)
                    s = e = date(y, monat(g[1]), int(g[0]))
                else:
                    vor = txt[max(0, a - 12):a].lower(); nach = txt[b:b + 8].strip().lower()
                    if "datum" in vor or nach.startswith("mehr"): continue   # Veroeffentlichungsdatum
                    if streng and not re.match(r"\s*\d{1,2}:\d{2}", txt[b:b + 8]): continue
                    s = e = date(int(g[2]), int(g[1]), int(g[0]))
            except (TypeError, ValueError):
                continue
            if e < s: continue
            belegt.append((a, b)); out.append((a, b, s, e))
    return out

def kandidaten(text, woerter, heute, streng=False, maxdist=130):
    """Liefert (wort, start, ende, ausschnitt, fenster), je Wort hoechstens 3 Treffer."""
    out = []
    for wort in woerter:
        n = 0
        for m in re.finditer(re.escape(wort), text, re.I):
            a0 = max(0, m.start() - 90); fenster = text[a0: m.end() + 220]
            if RAUSCHEN.search(fenster): continue
            ks, ke = m.start() - a0, m.end() - a0
            best = None
            for a, b, s, e in datum_treffer(fenster, heute, streng):
                if streng and s < heute + timedelta(MIN_VORLAUF): continue   # Kopfzeile der Seite zeigt das heutige Datum
                dist = max(0, a - ke) if a >= ke else max(0, ks - b) + 30
                if dist <= maxdist and (best is None or dist < best[0]): best = (dist, s, e)
            if not best: continue
            _, s, e = best
            if s < heute or s > heute + timedelta(520): continue
            out.append((wort, s, e, sauber(fenster, ks - 30, ke + 140).replace("|", "/"), fenster))
            n += 1
            if n >= 3: break
    return out

def d8(x): return date(int(x[:4]), int(x[4:6]), int(x[6:8]))

def uid_von(key): return f"{uuid.uuid5(uuid.NAMESPACE_URL, UID_PREFIX + key)}@events-dreieich"

def bekannt_laden(ohne_uids=()):
    """Liste (start, ende, titel_klein) aus Kalenderdatei (ohne die genannten UIDs), termine.json und eigene_termine.txt."""
    liste = []
    if os.path.exists(AUSGABE):
        txt = open(AUSGABE, encoding="utf-8").read().replace("\r\n ", "").replace("\n ", "")
        for blk in txt.split("BEGIN:VEVENT")[1:]:
            t = re.search(r"SUMMARY:(.*)", blk); s = re.search(r"DTSTART;VALUE=DATE:(\d{8})", blk)
            e = re.search(r"DTEND;VALUE=DATE:(\d{8})", blk); u = re.search(r"UID:(\S+)", blk)
            if u and u.group(1).strip() in ohne_uids: continue
            if t and s and e: liste.append((d8(s.group(1)), d8(e.group(1)) - timedelta(1), t.group(1).strip().lower()))
    if os.path.exists("termine.json"):
        try:
            for t in json.load(open("termine.json", encoding="utf-8")).get("termine", []):
                s = date.fromisoformat(t["start"]); e = date.fromisoformat(t.get("ende", t["start"]))
                liste.append((s, e, (t.get("titel") or t.get("name") or "").lower()))
        except Exception as ex:
            log(f"termine.json nicht lesbar: {ex}")
    if os.path.exists("eigene_termine.txt"):
        for z in open("eigene_termine.txt", encoding="utf-8").read().splitlines():
            p = [x.strip() for x in z.split("|")]
            if z.startswith("#") or z.startswith("-") or len(p) < 4: continue
            try: liste.append((date.fromisoformat(p[0]), date.fromisoformat(p[1] or p[0]), p[3].lower()))
            except ValueError: pass
    return liste

def ablehnungen_laden(pfad="ablehnungen.txt"):
    if not os.path.exists(pfad):
        with open(pfad, "w", encoding="utf-8") as f: f.write(ABL_START)
    return [z.strip().lower() for z in open(pfad, encoding="utf-8").read().splitlines() if z.strip() and not z.startswith("#")]

def ist_bekannt(s, e, wort, stadt, bekannt):
    w = wort.lower()
    toks = STADT_TOKEN.get(stadt, [stadt.split("-")[0][:6]])
    for ks, ke, t in bekannt:
        if ke < s - timedelta(1) or ks > e + timedelta(1) or w not in t: continue
        if not toks or any(x in t for x in toks) or (ks == s and ke == e): return True
    return False

def vorschlaege_laden(heute, bekannt, abl, pfad="vorschlaege.txt"):
    out, komm = {}, None
    if not os.path.exists(pfad): return out
    for z in open(pfad, encoding="utf-8").read().splitlines():
        if z.startswith("#>"): komm = z; continue
        if not z.strip() or z.startswith("#"): komm = None; continue
        p = [x.strip() for x in z.split("|")]
        if komm is None or len(p) < 4: continue
        try: s, e = date.fromisoformat(p[0]), date.fromisoformat(p[1])
        except ValueError: komm = None; continue
        k = komm[2:].strip().split(" | ")
        stadt, wort = k[0].strip(), (k[1].strip() if len(k) > 1 else "")
        if s >= heute and not ist_bekannt(s, e, wort, stadt, bekannt) and not any(x in (komm + " " + p[3]).lower() for x in abl):
            out[(s, e, p[3].lower())] = (komm, z, s)
        komm = None
    return out

def alt_laden(pfad="gefunden.json"):
    try:
        d = json.load(open(pfad, encoding="utf-8"))
        return list(d.get("gefunden", [])), list(d.get("auto", []))
    except Exception:
        return [], []

def behalten(alt, neu, heute):
    """Alte Eintraege, die schon vorbei sind (bis 190 Tage), bleiben; zukuenftige gelten nur, wenn neu wieder gefunden."""
    keys = {x["key"] for x in neu}
    out = []
    for x in alt:
        try: e = date.fromisoformat(x["ende"])
        except (KeyError, ValueError): continue
        if x.get("key") not in keys and heute - timedelta(190) <= e < heute: out.append(x)
    return out

MIN_VORLAUF = 3   # Tage: Markt-Termine muessen mindestens so weit in der Zukunft liegen (Seiten zeigen oben das heutige Datum)
AUTO_OHNE_JAHR = ["Winterzauber"]   # Datum auch ohne Jahr, wenn es zwischen 24. und 31.12. liegt

def auto_kandidaten(text, heute):
    out = kandidaten(text, AUTO_WOERTER, heute, streng=True)
    for k in kandidaten(text, AUTO_OHNE_JAHR, heute):
        s, e = k[1], k[2]
        if s < heute + timedelta(MIN_VORLAUF): continue
        if s.month == 12 and 24 <= s.day <= 31 and e.month == 12 and s <= e and e.day <= 31:
            gleich = [x for x in out if x[0] == k[0] and x[1] == s]
            if gleich and max(x[2] for x in gleich) >= e: continue   # laengerer Zeitraum gewinnt
            out = [x for x in out if x not in gleich] + [k]
    return out

def behalten_auto(alt, neu, heute):
    """Abgelaufene Markt-Eintraege bleiben bis 190 Tage, aber nur, wenn sie beim ersten Fund (ab) mindestens
    MIN_VORLAUF Tage in der Zukunft lagen. Eintraege ohne ab (aelter) fallen weg."""
    keys = {x["key"] for x in neu}
    out = []
    for x in alt:
        try:
            e = date.fromisoformat(x["ende"]); st = date.fromisoformat(x["start"]); ab = date.fromisoformat(x["ab"])
        except (KeyError, ValueError):
            continue
        if x.get("key") not in keys and heute - timedelta(190) <= e < heute and (st - ab).days >= MIN_VORLAUF: out.append(x)
    return out

def noch_gueltig(x, heute):
    try: return date.fromisoformat(x["ende"]) >= heute
    except (KeyError, ValueError): return False

def main():
    heute = date.today()
    q = json.load(open("quellen.json", encoding="utf-8"))
    alt_gef, alt_auto = alt_laden()

    # 1) "datum": feste Saetze
    gefunden, datum_fehler = {}, False
    for quelle in q.get("datum", []):
        try:
            text = als_text(hole(quelle["url"]))
            treffer = finde(quelle, text)
            if not treffer: log(f"KEIN TREFFER {quelle['url']}")
            for key, s, e, vorlage in treffer:
                eintrag = {"key": key, "start": s.isoformat(), "ende": e.isoformat(), "url": quelle["url"]}
                if vorlage: eintrag["vorlage"] = vorlage
                gefunden[key] = eintrag
                log(f"OK {key} {s} bis {e}")
        except Exception as ex:
            datum_fehler = True
            log(f"FEHLER {quelle['url']}: {ex}")
    neu_gef = list(gefunden.values())
    gef_liste = neu_gef + behalten(alt_gef, neu_gef, heute)
    if datum_fehler:     # Seite ausgefallen: bisherige Eintraege bleiben
        vorh = {x["key"] for x in gef_liste}
        gef_liste += [x for x in alt_gef if x.get("key") not in vorh and noch_gueltig(x, heute)]

    # 2) Beobachten: Maerkte automatisch, alles andere als Vorschlag
    ohne = {uid_von(x["key"]) for x in alt_auto if x.get("key")}
    bekannt = bekannt_laden(ohne); abl = ablehnungen_laden()
    bekannt_voll = bekannt_laden()   # inkl. Markt-Automatik: Vorschlaege dazu verschwinden
    bestand = vorschlaege_laden(heute, bekannt_voll, abl)
    auto_neu, auto_fehler, neu = {}, set(), 0
    for quelle in q.get("beobachten", []) + q.get("grossstaedte", []):
        url = quelle["url"]; stadt = quelle.get("stadt", "")
        host = urllib.parse.urlparse(url).netloc
        if host in LAHM:
            log(f"UEBERSPRUNGEN (Server antwortet nicht) {url}"); auto_fehler.add(url); continue
        try:
            text = als_text(hole(url))
            if len(text) < 800: log(f"WENIG TEXT (vermutlich nur JavaScript) {url}")
            else: log(f"OK {len(text)} Zeichen {url}")
            name = STADT_NAME.get(stadt, stadt.capitalize())
            auto_spans = set()
            if stadt in AUTO_STAEDTE and quelle.get("art") in AUTO_ARTEN:
                for wort, s, e, ausschnitt, fenster in auto_kandidaten(text, heute):
                    titel = f"{wort} {name}".strip()
                    key = f"auto|{stadt}|{wort.lower()}|{s.isoformat()}"
                    if key in auto_neu or ist_bekannt(s, e, wort, stadt, bekannt): continue
                    if any(x in (titel + " " + fenster).lower() for x in abl): continue
                    auto_neu[key] = {"key": key, "start": s.isoformat(), "ende": e.isoformat(),
                                     "name": titel, "pre": "▼ " if stadt == "dreieich" else "",
                                     "stadt": stadt, "url": url, "ab": heute.isoformat()}
                    auto_spans.add((wort.lower(), s))
                    log(f"AUTO {titel} {s} bis {e}")
            if stadt in OHNE_VORSCHLAEGE: continue
            for wort, s, e, ausschnitt, fenster in kandidaten(text, q.get("stichworte", []), heute):
                if (wort.lower(), s) in auto_spans: continue
                titel = f"{wort} {name}".strip()
                key = (s, e, titel.lower())
                if key in bestand or ist_bekannt(s, e, wort, stadt, bekannt_voll): continue
                if any(x in (titel + " " + fenster).lower() for x in abl): continue
                hinweis = "ueber 7 Tage: Pfeil-Termine in termine.json" if (e - s).days >= 7 else "-"
                bestand[key] = (f"#> {stadt} | {wort} | {hinweis} | {url} | {ausschnitt}", f"{s} | {e} | ? | {titel} | ", s)
                neu += 1
        except Exception as ex:
            log(f"FEHLER {url}: {ex}")
            auto_fehler.add(url)
            if "timed out" in str(ex): LAHM.add(host)

    neu_auto = list(auto_neu.values())
    auto = neu_auto + behalten_auto(alt_auto, neu_auto, heute)
    vorh = {x["key"] for x in auto}
    for x in alt_auto:   # Seite ausgefallen: Eintraege dieser Seite bleiben
        if x.get("url") in auto_fehler and x.get("key") not in vorh and noch_gueltig(x, heute): auto.append(x)
    json.dump({"gefunden": gef_liste, "auto": auto}, open("gefunden.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"AUTO {len(auto)} Markt-Eintraege, GEFUNDEN {len(gef_liste)}")

    eintraege = sorted(bestand.values(), key=lambda x: x[2])[:250]
    with open("vorschlaege.txt", "w", encoding="utf-8") as f:
        f.write(KOPF.format(heute=heute))
        for komm, zeile, _ in eintraege: f.write(komm + "\n" + zeile + "\n\n")
    log(f"VORSCHLAEGE {len(eintraege)} offen, davon {neu} neu")
    with open("quellen-log.txt", "w", encoding="utf-8") as f:
        f.write(f"# Lauf vom {heute}\n" + "\n".join(LOG) + "\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:      # nie den Kalender gefaehrden, aber den Fehler sichtbar machen
        print("Quellen-Abfrage abgebrochen:", ex)
        try:
            with open("quellen-log.txt", "w", encoding="utf-8") as f:
                f.write(f"# Lauf vom {date.today()}\nABGEBROCHEN: {ex}\n\n{traceback.format_exc()}\n" + "\n".join(LOG) + "\n")
        except Exception:
            pass
