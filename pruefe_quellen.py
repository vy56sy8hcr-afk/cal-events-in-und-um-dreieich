#!/usr/bin/env python3
"""Liest taeglich die Quellen aus quellen.json.
- "datum": korrigiert bekannte Termine -> gefunden.json
- "beobachten"/"grossstaedte": sucht Stichworte mit Datum und schreibt NEUE Treffer als
  fertige Zeilen (Format eigene_termine.txt) in vorschlaege.txt. Alte Vorschlaege bleiben stehen.
  Nicht aufgenommen werden: Termine, die schon im Kalender, in termine.json oder
  eigene_termine.txt stehen, und alles, was zu einem Begriff aus ablehnungen.txt passt.
Faellt eine Seite aus, passiert nichts: der Kalender bleibt unveraendert.
Protokoll: quellen-log.txt"""
import html as htmllib, json, os, re, time, urllib.parse, urllib.request
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
DATUM = re.compile(r"\b\d{1,2}\.\s?(?:\d{1,2}\.|(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember))(?:\s?\d{2,4})?")
LOG = []
LAHM = set()   # Server, die nicht antworten: weitere Seiten werden uebersprungen
RAUSCHEN = re.compile(r"Verkehrsbehinderung|Verkehrsinfo|Straßensperr|Sperrung|Bekanntmachung", re.I)
AUSGABE = "cal-events-in-und-um-dreieich.ics"
STADT_NAME = {"neu-isenburg": "N-I", "dreieich": "", "bad-homburg": "Bad Homburg", "fachwerkstrasse": "", "apfelweinroute": ""}
STADT_TOKEN = {"dreieich": ["▼"], "neu-isenburg": ["n-i", "isenburg"], "bad-homburg": ["homburg"],
               "fachwerkstrasse": [], "apfelweinroute": []}
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
    """Gibt Liste (key, start, ende) zurueck."""
    out = []
    for m in re.finditer(quelle["muster"], text, re.I):
        g = m.groups()
        try:
            if quelle["typ"] == "einzeltag":
                t, mo, j = int(g[0]), monat(g[1]), int(g[2]); s = e = date(j, mo, t)
            elif quelle["typ"] == "zeitraum":      # 28. - 30. August 2026
                t1, t2, mo, j = int(g[0]), int(g[1]), monat(g[2]), int(g[3])
                s, e = date(j, mo, t1), date(j, mo, t2)
            elif quelle["typ"] == "zeitraum_num":   # 27.08. bis 30.08.2027
                d1, m1, d2, m2, j = (int(x) for x in g[:5])
                s, e = date(j, m1, d1), date(j, m2, d2)
            else:
                continue
        except (TypeError, ValueError):
            continue
        heute = date.today()
        if not (heute - timedelta(400) <= s <= heute + timedelta(700)) or e < s: continue
        out.append((quelle["key"].format(jahr=s.year), s, e))
    return out

def datum_treffer(txt, heute):
    """Alle Datumsangaben im Text: Liste (pos_von, pos_bis, start, ende)."""
    wj = re.search(r"\b(20\d\d)\b", txt)
    wj = int(wj.group(1)) if wj else None
    belegt, out = [], []
    for art, mu in MUSTER:
        for m in mu.finditer(txt):
            a, b = m.span()
            if any(a < y and x < b for x, y in belegt): continue
            g = m.groups()
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
                    s = e = date(int(g[2]), int(g[1]), int(g[0]))
            except (TypeError, ValueError):
                continue
            if e < s: continue
            belegt.append((a, b)); out.append((a, b, s, e))
    return out

def d8(x): return date(int(x[:4]), int(x[4:6]), int(x[6:8]))

def bekannt_laden():
    """Liste (start, ende, titel_klein) aus Kalenderdatei, termine.json und eigene_termine.txt."""
    liste = []
    if os.path.exists(AUSGABE):
        txt = open(AUSGABE, encoding="utf-8").read().replace("\r\n ", "").replace("\n ", "")
        for blk in txt.split("BEGIN:VEVENT")[1:]:
            t = re.search(r"SUMMARY:(.*)", blk); s = re.search(r"DTSTART;VALUE=DATE:(\d{8})", blk)
            e = re.search(r"DTEND;VALUE=DATE:(\d{8})", blk)
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

def main():
    heute = date.today()
    q = json.load(open("quellen.json", encoding="utf-8"))
    gefunden = {}
    for quelle in q.get("datum", []):
        try:
            text = als_text(hole(quelle["url"]))
            treffer = finde(quelle, text)
            if not treffer: log(f"KEIN TREFFER {quelle['url']}")
            for key, s, e in treffer:
                gefunden[key] = {"key": key, "start": s.isoformat(), "ende": e.isoformat()}
                log(f"OK {key} {s} bis {e}")
        except Exception as ex:
            log(f"FEHLER {quelle['url']}: {ex}")
    json.dump({"gefunden": list(gefunden.values())}, open("gefunden.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    bekannt = bekannt_laden(); abl = ablehnungen_laden()
    bestand = vorschlaege_laden(heute, bekannt, abl)
    neu = 0
    for quelle in q.get("beobachten", []) + q.get("grossstaedte", []):
        url = quelle["url"]; stadt = quelle.get("stadt", "")
        host = urllib.parse.urlparse(url).netloc
        if host in LAHM:
            log(f"UEBERSPRUNGEN (Server antwortet nicht) {url}"); continue
        try:
            text = als_text(hole(url))
            if len(text) < 800: log(f"WENIG TEXT (vermutlich nur JavaScript) {url}")
            else: log(f"OK {len(text)} Zeichen {url}")
            for wort in q.get("stichworte", []):
                n = 0
                for m in re.finditer(re.escape(wort), text, re.I):
                    a0 = max(0, m.start() - 90); fenster = text[a0: m.end() + 220]
                    if RAUSCHEN.search(fenster): continue
                    ks, ke = m.start() - a0, m.end() - a0
                    best = None
                    for a, b, s, e in datum_treffer(fenster, heute):
                        if s < heute or s > heute + timedelta(520): continue
                        dist = max(0, a - ke) if a >= ke else max(0, ks - b) + 30
                        if dist <= 130 and (best is None or dist < best[0]): best = (dist, s, e)
                    if not best: continue
                    _, s, e = best
                    titel = f"{wort} {STADT_NAME.get(stadt, stadt.capitalize())}".strip()
                    key = (s, e, titel.lower())
                    if key in bestand or ist_bekannt(s, e, wort, stadt, bekannt): continue
                    if any(x in (titel + " " + fenster).lower() for x in abl): continue
                    hinweis = "ueber 7 Tage: Pfeil-Termine in termine.json" if (e - s).days >= 7 else "-"
                    ausschnitt = fenster[max(0, ks - 30): ke + 140].strip().replace("|", "/")
                    bestand[key] = (f"#> {stadt} | {wort} | {hinweis} | {url} | {ausschnitt}", f"{s} | {e} | ? | {titel} | ", s)
                    neu += 1; n += 1
                    if n >= 3: break
        except Exception as ex:
            log(f"FEHLER {url}: {ex}")
            if "timed out" in str(ex): LAHM.add(host)
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
    except Exception as ex:      # nie den Kalender gefaehrden
        print("Quellen-Abfrage abgebrochen:", ex)
