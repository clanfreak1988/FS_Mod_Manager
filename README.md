# FS Mod Manager

Verwaltet Mods für Farming Simulator: sammelt Mod-ZIPs an einem festen Ort
("Sammelordner"), aktiviert per Konfiguration nur eine Auswahl davon im
FS-Mod-Ordner (über symbolische Links) und merkt sich beliebig viele solcher
Konfigurationen (z.B. pro Savegame).

Diese Anleitung richtet sich an Endanwender – zur Installation und Bedienung.

---

## Inhalt

- [Installation unter Linux](#installation-unter-linux)
- [Installation unter Windows](#installation-unter-windows)
- [Ersteinrichtung](#ersteinrichtung)
- [Bedienung](#bedienung)
- [Problembehandlung](#problembehandlung)

---

## Installation unter Linux

Es gibt ein fertiges **AppImage** – keine Installation nötig.

1. `FSModManager-x86_64.AppImage` herunterladen.
2. Ausführbar machen:
   ```
   chmod +x FSModManager-x86_64.AppImage
   ```
3. Starten:
   ```
   ./FSModManager-x86_64.AppImage
   ```

Die Datei kann an einen beliebigen Ort verschoben werden (z.B. `~/Anwendungen/`);
sie enthält alles Nötige und benötigt keine separate Python-Installation.

Einstellungen und Log-Datei landen unter `~/.local/share/FSModManager/`.

---

## Installation unter Windows

Es gibt eine fertige **FSModManager.exe** – keine Installation nötig.

1. `FSModManager.exe` herunterladen.
2. Starten (Doppelklick). Windows SmartScreen kann beim ersten Start warnen,
   da die exe nicht signiert ist – über **"Weitere Informationen" →
   "Trotzdem ausführen"** bestätigen.

Die Datei kann an einen beliebigen Ort verschoben werden; sie enthält alles
Nötige und benötigt keine separate Python-Installation.

**Wichtig – symbolische Links unter Windows:**
Der Mod Manager aktiviert Mods über symbolische Links. Windows verlangt dafür
eines von beidem:

- **Entwicklermodus aktivieren** (empfohlen, einmalig):
  Einstellungen → System → Für Entwickler → Entwicklermodus einschalten.
- Oder das Programm **als Administrator** starten (jedes Mal nötig).

Ohne eines von beiden erscheint beim Aktivieren einer Konfiguration eine
Fehlermeldung mit genau diesem Hinweis.

Mindestvoraussetzung ist **Windows 11**. Einstellungen und Log-Datei landen
unter `%APPDATA%\FSModManager\`.

---

## Ersteinrichtung

Beim allerersten Start (keine gespeicherten Einstellungen vorhanden) fragt
der Mod Manager drei Pfade ab. Der "Weiter"-Button wird erst aktiv, wenn alle
drei tatsächlich existieren (grüne statt rote Beschriftung):

| Pfad | Bedeutung |
|---|---|
| **FS Mod-Ordner** | Der Mods-Ordner, den Farming Simulator selbst einliest (üblicherweise `Dokumente\My Games\FarmingSimulator20XX\mods`) |
| **Sammelordner** | Ein frei wählbarer Ordner, in dem der Mod Manager *alle* jemals hinzugefügten Mods dauerhaft aufbewahrt – unabhängig davon, welche Konfiguration gerade aktiv ist |
| **Savegame-Pfad** | Der Ordner mit den `savegameX`-Unterordnern (üblicherweise `Dokumente\My Games\FarmingSimulator20XX`) |

Direkt danach wird optional angeboten, aus allen vorhandenen Savegames
automatisch je eine Konfiguration zu erstellen.

Alle drei Pfade lassen sich später jederzeit über **Einstellungen** ändern.
Wird dort ein Pfad geändert, fragt der Mod Manager, ob die vorhandenen
Dateien an den neuen Ort mit verschoben werden sollen.

---

## Bedienung

### Grundprinzip

- **Verfügbar** (linke Spalte): alle Mods im Sammelordner, die *nicht* Teil
  der aktuellen Konfiguration sind.
- **Ausgewählt** (rechte Spalte): die Mods der aktuellen Konfiguration.
- Mods zwischen beiden Spalten verschieben per Doppelklick, per Drag & Drop,
  oder über die Pfeil-Buttons (→/← je markierte Mods, ⇒/⇐ alle auf einmal).
- Über die Suchfelder oberhalb jeder Spalte lässt sich nach Titel filtern.

### Mehrere Spielversionen

Ganz links in der Toolbar steht der Button **"Spiel: FS25 ▾"**. Darüber lassen
sich mehrere Farming-Simulator-Installationen parallel verwalten – jede mit
eigenem Mod-Ordner, eigenem Sammelordner und damit auch eigenen
Konfigurationen (die Konfigurationsdateien liegen neben dem Sammelordner).

Das Menü des Buttons enthält:

- die vorhandenen Spielversionen; ein Klick wechselt sofort dorthin
  (Mod-Listen, Konfigurationsauswahl und Fenstertitel stellen sich um),
- **"Neue Spielversion…"**: Dialog mit einer Vorlage-Auswahl (FS25, FS22, …),
  die Name und alle drei Pfade aus dem Standard-Ordner der jeweiligen Version
  vorbelegt. Fehlt der Sammelordner noch, legt ihn der Button **"Anlegen"** an,
- **"'…' bearbeiten…"**: Name und Pfade der aktiven Spielversion ändern,
- **"Spielversion löschen"**: entfernt nur den Eintrag – Mod-Ordner,
  Sammelordner und Konfigurationen bleiben unangetastet. Die gerade aktive
  Spielversion lässt sich nicht löschen, dafür vorher wechseln.

Beim ersten Start mit dieser Version wird die bisherige Einrichtung automatisch
zur ersten Spielversion (benannt nach ihrem Spielordner, z.B. "FS25") – es ist
nichts weiter zu tun.

Zu beachten:

- Zwei Spielversionen dürfen sich weder Mod- noch Sammelordner teilen; der
  Mod Manager lehnt das beim Anlegen ab.
- Beim Wechsel bleiben die Symlinks der vorherigen Spielversion in deren
  Mod-Ordner liegen. Das ist Absicht: jedes Spiel behält seinen zuletzt
  aktivierten Stand.
- Das Ändern der Pfade im Spielversions-Dialog verschiebt keine Dateien.
  Dafür gibt es die Pfadfelder unter **Einstellungen**, die beim Ändern
  anbieten, die Mods mitzunehmen.

### Neue Mods hinzufügen

Neue ZIP-Dateien einfach in den **FS Mod-Ordner** legen und **"Neu laden"**
klicken. Der Mod Manager verschiebt sie automatisch in den Sammelordner und
verlinkt sie zurück. Liegt dort bereits eine Datei gleichen Namens, erscheint
ein Dialog zur Konfliktlösung (siehe unten). Neu erkannte Mods werden in
beiden Spalten kurz farblich hervorgehoben.

Werden beim Programmstart neue Mods eingesammelt, erscheint anschließend –
sofern schon Konfigurationen existieren – das Fenster
**"Neue Mods gefunden"**: eine Kreuztabelle mit den neuen Mods als Zeilen und
den Konfigurationen als Spalten. Damit lässt sich in einem Rutsch festlegen,
welcher Mod in welche Konfiguration soll – ein Mod kann in mehrere
Konfigurationen, eine Konfiguration kann mehrere Mods aufnehmen:

- Ein Klick auf einen **Spaltenkopf** kreuzt die ganze Spalte an bzw. ab
  (alle neuen Mods in dieser Konfiguration).
- Ein Klick auf einen **Zeilenkopf** entsprechend die ganze Zeile
  (dieser Mod in allen Konfigurationen).
- **"Alle Mods zu allen Konfigurationen"** kreuzt alles an,
  **"Auswahl aufheben"** setzt alles zurück.
- **"Hinzufügen"** schreibt die Zuordnung in die Konfigurationsdateien,
  **"Überspringen"** ändert nichts.

Karten sind in der Tabelle mit *(Karte)* gekennzeichnet. Da eine Konfiguration
immer nur eine Karte enthalten darf, wird eine Karte für Konfigurationen, die
bereits eine haben, übersprungen – mit einem Hinweis, welche das betrifft.

### Konfigurationen

Über die Toolbar oben: **Neu / Umbenennen / Kopieren / Löschen** sowie das
Auswahlfeld, um zwischen bestehenden Konfigurationen zu wechseln. Eine
Konfiguration ist einfach eine benannte Liste von Mod-Dateinamen (z.B. eine
pro Savegame oder Multiplayer-Server).

- **Speichern**: aktuellen Stand der Spalte "Ausgewählt" in der aktiven
  Konfiguration sichern.
- **Aktivieren**: die gespeicherte Konfiguration tatsächlich im FS-Mod-Ordner
  scharfschalten (legt die symbolischen Links an). Erst danach sieht
  Farming Simulator selbst die Auswahl.

### Als ZIP exportieren

Packt alle Mods aus "Ausgewählt" in eine einzelne ZIP-Datei, um sie z.B. an
andere Spieler eines Servers weiterzugeben.

### Savegame importieren

Liest die Mod-Liste aus einer `careerSavegame.xml` aus und legt daraus eine
neue Konfiguration an (Mods, die nur Teil des Spiels selbst sind, werden
automatisch herausgefiltert).

### Eingabegeräte

Öffnet einen Dialog, der veraltete Tasten-/Achsen-Zuordnungen für ein
bestimmtes Eingabegerät (Lenkrad, Joystick, o.ä.) aus der `inputBinding.xml`
entfernt – nützlich, wenn ein Gerät getauscht oder abgezogen wurde und FS
alte Zuordnungen sonst dauerhaft mitschleppt. Vor dem Entfernen wird
automatisch eine Sicherungskopie der Datei angelegt.

### Rechtsklick auf einen Mod

- **Löschen…**: entfernt den Mod endgültig aus dem Sammelordner (nach
  Bestätigung). Ist er gerade aktiv, wird auch der Link im FS-Mod-Ordner
  entfernt. Referenzen in gespeicherten Konfigurationen werden ebenfalls
  bereinigt.
- **Datei richtig benennen…** (nur bei Mods mit ungültigem Dateinamen,
  rot markiert): Farming Simulator erlaubt in ZIP-Dateinamen nur Buchstaben,
  Ziffern und Unterstrich `_`, und das erste Zeichen darf keine Ziffer sein
  (z.B. `FS25_Mod (1).zip` wird von FS abgelehnt). Dieser Punkt schlägt einen
  passenden Namen vor und benennt die Datei nach Bestätigung um.

### Konfliktlösung (beim Sammeln neuer Mods oder beim Umbenennen)

Existiert am Ziel bereits eine Datei mit demselben Namen, erscheint ein
Dialog mit Vergleich (Größe, Änderungsdatum, Mod-Version) und drei Optionen:

- **Neue übernehmen**: ersetzt die vorhandene Datei durch die neue.
- **Vorhandene behalten**: verwirft die neue Datei (wird gelöscht),
  die vorhandene bleibt unverändert.
- **Überspringen**: nichts wird verändert, die neue Datei bleibt einfach im
  FS-Mod-Ordner liegen bzw. der ungültige Name wird nicht geändert.

### Einstellungen

Neben den drei Pfaden aus der Ersteinrichtung: Icon-Spalte in den Mod-Listen
ein-/ausblenden, sowie das Design (System / Hell / Dunkel).

### "?"-Menü

- **Info**: Versionsangabe.
- **Log-Datei öffnen** / **Log-Ordner öffnen**: für Fehlersuche – hilfreich,
  wenn man Support-Anfragen stellt.

---

## Problembehandlung

**"Symbolischer Link konnte nicht erstellt werden: Fehlende Berechtigung"**
→ Unter Windows: Entwicklermodus aktivieren oder das Programm als
Administrator starten (siehe [Installation unter Windows](#installation-unter-windows)).

**"Quelle und Ziel liegen auf unterschiedlichen Laufwerken"**
→ FS Mod-Ordner und Sammelordner müssen auf demselben Laufwerk liegen
(symbolische Links können nicht laufwerksübergreifend erstellt werden).

**Mod erscheint rot markiert in der Liste**
→ Der Dateiname ist für Farming Simulator ungültig (siehe
"Datei richtig benennen…" oben). FS würde diesen Mod sonst mit einer
Fehlermeldung ablehnen.

---

## Hinweis

Dieses Programm wurde mit Unterstützung von KI (Künstlicher Intelligenz)
entwickelt.
