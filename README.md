# Events in und um Dreieich (Dreieich, Langen, Neu-Isenburg)

Abo-Link (Kalender-App, “Kalender per URL hinzufügen”):
<https://raw.githubusercontent.com/vy56sy8hcr-afk/cal-events-in-und-um-dreieich/main/cal-events-in-und-um-dreieich.ics>

- `build_ics.py` berechnet alle Termine nach Rhythmus-Regeln (Kerben, Weinfest, Weihnachtsmärkte, …).
- `termine.json` enthält bestätigte Termine. Gleicher `key` ersetzt den Rhythmus-Termin, `"skip": true` löscht ihn.
- Der Workflow läuft täglich, verschiebt das Fenster (heute -6 bis +16 Monate) und speichert die ICS.
