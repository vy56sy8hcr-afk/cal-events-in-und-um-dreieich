#!/usr/bin/env python3
"""Liest taeglich die Quellen aus quellen.json.
- "datum": korrigiert bekannte Termine -> gefunden.json
- "beobachten": sucht Stichworte mit Datum -> vorschlaege.txt (nur Vorschlaege)
Faellt eine Seite aus, passiert nichts: der Kalender bleibt unveraendert.
Protokoll: quellen-log.txt"""
import html as htmllib, json, re, time, urllib.parse, urllib.request
from datetime import date, timedelta

MONATE = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
          "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}
DATUM = re.compile(r"\b\d{1,2}\.\s?(?:\d{1,2}\.|(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember))(?:\s?\d{2,4})?")
LOG = []
LAHM = set()   # Server, die nicht antworten: weitere Seiten werden uebersprungen
RAUSCHEN = re.compile(r"Verkehrsbehinderung|Verkehrsinfo|Straßensperr|Sperrung|Bekanntmachung", re.I)

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

def main():
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

    vorschlaege = []
    for quelle in q.get("beobachten", []) + q.get("grossstaedte", []):
        url = quelle["url"]
        host = urllib.parse.urlparse(url).netloc
        if host in LAHM:
            log(f"UEBERSPRUNGEN (Server antwortet nicht) {url}"); continue
        try:
            text = als_text(hole(url))
            if len(text) < 800: log(f"WENIG TEXT (vermutlich nur JavaScript) {url}")
            else: log(f"OK {len(text)} Zeichen {url}")
            gesehen = set()
            for wort in q.get("stichworte", []):
                n = 0
                for m in re.finditer(re.escape(wort), text, re.I):
                    fenster = text[max(0, m.start() - 90): m.end() + 150]
                    if DATUM.search(fenster) and not RAUSCHEN.search(fenster) and fenster[:60] not in gesehen:
                        gesehen.add(fenster[:60]); n += 1
                        vorschlaege.append(f"{quelle.get('stadt','')} | {wort} | {fenster.strip()} | {url}")
                    if n >= 3: break
        except Exception as ex:
            log(f"FEHLER {url}: {ex}")
            if "timed out" in str(ex): LAHM.add(host)
    with open("vorschlaege.txt", "w", encoding="utf-8") as f:
        f.write(f"# Vorschlaege vom {date.today()} - nur zur Ansicht, nichts davon steht automatisch im Kalender\n")
        f.write("\n".join(vorschlaege[:300]) + "\n")
    with open("quellen-log.txt", "w", encoding="utf-8") as f:
        f.write(f"# Lauf vom {date.today()}\n" + "\n".join(LOG) + "\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:      # nie den Kalender gefaehrden
        print("Quellen-Abfrage abgebrochen:", ex)
