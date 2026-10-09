# Events in und um Dreieich (Dreieich, Langen, Neu-Isenburg)

Abo-Link (Kalender-App, “Kalender per URL hinzufügen”):
<https://raw.githubusercontent.com/vy56sy8hcr-afk/cal-events-in-und-um-dreieich/main/cal-events-in-und-um-dreieich.ics>

- `build_ics.py` berechnet alle Termine nach Rhythmus-Regeln (Kerben, Weinfest, Weihnachtsmärkte, …).
- `termine.json` enthält bestätigte Termine. Gleicher `key` ersetzt den Rhythmus-Termin, `"skip": true` löscht ihn.
- Der Workflow läuft täglich, verschiebt das Fenster (heute -6 bis +16 Monate) und speichert die ICS.

Hier der Text für deine README.md. Du ersetzt damit den ganzen Inhalt der Datei:

README Veranstaltungskalender

Welche Datei wofür?

build_ics.py enthält die Regeln für Termine, die jedes Jahr nach einem festen Muster wiederkommen, zum Beispiel das Countryfest an Himmelfahrt. Auch feste Notizen zu einem Rhythmus-Termin gehören dorthin.

termine.json enthält bestätigte Daten für Termine, die build_ics.py schon kennt. Ein Eintrag mit dem gleichen Namen (key) ersetzt die Regel. Mit “vorlaeufig” darf die Quellenabfrage das Datum noch überschreiben, mit “skip” fällt der Termin ganz weg. Pfeil-Termine wie Kunsttage oder Burgfestspiele laufen nur über diese Datei.

eigene_termine.txt enthält neue Einzeltermine ohne Regel. Jede Zeile ist ein Termin, die Felder trennst du mit senkrechten Strichen: von | bis | modus | titel | notiz. Zeilen mit # am Anfang werden ignoriert. Das Datum schreibst du als JJJJ-MM-TT.

Beispiele für eigene_termine.txt

Fester Termin an einem Tag: Das Neujahrskonzert am 17.01.2027 ist sicher. Du schreibst 2027-01-17 | 2027-01-17 | ! | ▼⭐️5oNeujahrskonzert | und lässt die Notiz leer. Das Datum steht zweimal, weil es nur ein Tag ist.

Fester Termin über mehrere Tage mit Notiz: Ein Fest geht sicher vom 4. bis 6. Juni 2027. Du schreibst 2027-06-04 | 2027-06-06 | ! | ▼🎈Beispielfest | Beginn 11 Uhr. Links steht der erste Tag, daneben der letzte.

Vorläufiger Termin: Das Hooschebaa-Fest 2027 ist noch nicht bestätigt. Du schreibst 2027-06-04 | 2027-06-06 | ? | ▼🎈Hooschebaa-Fest | und lässt die Notiz leer. Das Fragezeichen sorgt dafür, dass er später gegen die Quellen abgeglichen wird.

Termin löschen: Der Rathaussturm N-I 2027 fällt aus. Du schreibst eine Zeile aus Minus, Leerzeichen und dem Namen mit Jahr: - rathaussturm-ni-2027. Ein Datum brauchst du nicht. Die anderen Jahre bleiben.

Wichtig

Die Striche zwischen den Feldern stehen auch dann, wenn ein Feld leer bleibt.

Die Zeilen müssen in der Datei stehen bleiben. Der Kalender wird bei jedem Lauf komplett neu gebaut. Wer eine Zeile löscht, entfernt den Termin wieder. Alte Termine stören nicht, das Fenster blendet sie nach sechs Monaten von selbst aus.

termine.json und eigene_termine.txt änderst du nur von Hand. Kein Skript schreibt dort hinein. Wer eine dieser Dateien mit einer älteren Fassung ersetzt, verliert seine Änderungen.

Nach jeder Änderung: Commit changes, dann den Workflow mit “Run workflow” starten.

Gib Bescheid, wenn du es kürzer oder anders aufgebaut haben möchtest.
