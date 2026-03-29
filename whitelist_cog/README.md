# Player Access Control Cog

Ein fortschrittliches Player-Access-Management-System für RedBot mit interaktiven Dropdown-Menüs, Suchfunktion, Prioritätssystem und umfassenden Verwaltungsfunktionen.

**Keine Slash Commands** - Verwendet ausschließlich Prefix-Befehle!

## ✨ Hauptmerkmale

- 🎮 **Interaktives Dropdown-Menü** - Spieler einfach auswählen und verwalten
- 🔍 **Suchfunktion** - Schnelle Spielersuche über Modal-Dialog
- ⭐ **Prioritätssystem** - 6 Prioritätsstufen (0-5) mit Limits
- 📝 **Notizfunktion** - Interne Notizen zu jedem Spieler speichern
- 📊 **Statistiken** - Detaillierte Übersichten und Analysen
- 📋 **Umfassendes Logging** - Alle Aktionen werden protokolliert
- 🎭 **Rollenzuweisung** - Automatische Rolle bei Whitelist
- 💬 **Benachrichtigungen** - DMs und Willkommensnachrichten
- 📤 **Export** - Whitelist als Textdatei exportieren
- 🧹 **Cleanup** - Inaktive Spieler automatisch entfernen
- 🔒 **Berechtigungssystem** - Mehrere Admin-Rollen konfigurierbar

## 📦 Installation

1. Cog-Ordner zu RedBot hinzufügen:
```
[p]cog installpath /workspace/whitelist_cog
```

2. Cog laden:
```
[p]load player_access
```

3. Zugangsrolle konfigurieren:
```
[p]pa setrole @DeineWhitelistRolle
```

4. Optional: Log-Kanal einrichten:
```
[p]pa setlogchannel #log-kanal
```

## 🎮 Befehle

### Hauptbefehl
- `[p]playeraccess` - Öffnet das interaktive Hauptmenü
- `[p]pa` - Kurzform
- `[p]access` - Alternative

### Konfiguration (Admin-only)
- `[p]pa config` - Zeigt die aktuelle Konfiguration
- `[p]pa setrole @Rolle` - Setzt die Zugangsrolle für gewhitelisted Spieler
- `[p]pa addadminrole @Rolle` - Fügt eine Admin-Rolle hinzu
- `[p]pa removeadminrole @Rolle` - Entfernt eine Admin-Rolle
- `[p]pa setlogchannel #Kanal` - Setzt den Log-Kanal
- `[p]pa disablelogs` - Deaktiviert das Logging

### Verwaltung
- `[p]pa stats` - Zeige detaillierte Statistiken
- `[p]pa export` - Exportiere die Whitelist als Datei
- `[p]pa cleanup [Tage]` - Entferne inaktive Spieler (Standard: 30 Tage)

## 🎯 Menü-Funktionen

### Dropdown-Menü
- Wähle einen Spieler aus der Liste
- Zeigt Status (✅ gewhitelisted / ⏳ ausstehend) und Priorität
- 8 Spieler pro Seite

### Filter-Buttons
- **📊 Alle** - Zeigt alle Spieler
- **✅ Whitelisted** - Nur gewhitelisted Spieler
- **⏳ Ausstehend** - Nur ausstehende Spieler

### Suchfunktion
- **🔍 Suche** Button öffnet Suchmodal
- Gib Name oder ID ein
- Filtert die Liste in Echtzeit

### Seiten-Navigation
- **⬅️** / **➡️** - Zwischen Seiten navigieren
- **🔄 Aktualisieren** - Liste neu laden
- **📈 Statistiken** - Übersicht anzeigen
- **❌ Schließen** - Menü schließen

### Spieler-Aktionen
Nach Auswahl eines Spielers:
- **✅ Whitelisten** - Öffnet Modal mit Grund, Priorität, Notizen
- **❌ Entfernen** - Mit Bestätigungsdialog
- **📝 Notiz bearbeiten** - Interne Notizen pflegen

## ⚙️ Konfigurationsoptionen

### Rollen
- `access_role` - Rolle die gewhitelisted Spieler erhalten
- `admin_roles` - Liste der Rollen mit Zugriffsberechtigung

### Logging
- `log_channel` - Kanal für Action-Logs
- Alle Aktionen werden mit Timestamp und User protokolliert

### Prioritäts-Limits
Standardmäßig konfiguriert:
- Priorität 5: Max 5 Spieler
- Priorität 4: Max 10 Spieler
- Priorität 3: Max 20 Spieler

### Benachrichtigungen
- `welcome_message` - Sendet Willkommensnachricht im Channel
- `dm_on_whitelist` - Sendet DM an den Spieler

## 🔐 Berechtigungen

Folgende Benutzer können das System verwenden:
- Server-Owner
- Benutzer mit Administrator-Rechten
- Benutzer mit einer konfigurierten Admin-Rolle

## 📊 Statistiken

Das Statistik-Feature zeigt:
- Gesamtanzahl Spieler
- Gewhitelisted vs. Ausstehend
- Prioritäts-Verteilung
- Neue Spieler (letzte 7 Tage)
- Top Moderatoren (meiste Whitelists)

## 💡 Tipps

1. **Ersteinrichtung:**
   ```
   [p]pa setrole @Whitelisted
   [p]pa setlogchannel #mod-logs
   [p]pa addadminrole @Moderator
   ```

2. **Regelmäßige Wartung:**
   ```
   [p]pa cleanup 30  # Entfernt Spieler nach 30 Tagen Inaktivität
   [p]pa export      # Backup erstellen
   ```

3. **Prioritäten nutzen:**
   - 0: Standard-Spieler
   - 1-2: Aktive Spieler
   - 3-4: VIP-Spieler
   - 5: Besondere Fälle

## 🛠️ Fehlerbehebung

**Cog lädt nicht:**
- Stelle sicher, dass der Pfad korrekt ist
- Überprüfe die Python-Syntax mit `python -m py_compile player_access.py`

**Menü reagiert nicht:**
- Überprüfe die Bot-Berechtigungen (Messages, Embeds, Components)
- Stelle sicher, dass der User Berechtigungen hat

**Rolle wird nicht zugewiesen:**
- Rolle muss unterhalb der Bot-Rolle sein
- Bot benötigt "Manage Roles" Berechtigung

## 📝 Datenstruktur

Gespeicherte Daten pro Spieler:
- `id` - Eindeutige Spieler-ID
- `name` - Spielername
- `discord_id` - Discord User ID (falls verknüpft)
- `whitelisted` - Boolean Status
- `priority` - Prioritätsstufe (0-5)
- `role_name` - Name der zugewiesenen Rolle
- `added_by` - User ID des Moderators
- `reason` - Grund für Whitelist
- `notes` - Interne Notizen
- `timestamp` - Zeitpunkt der Whitelist
- `last_seen` - Letzte Aktivität

## 🔄 Updates & Wartung

Die Daten werden persistent in der RedBot-Config gespeichert und bleiben auch nach Neustarts erhalten.

---

**Entwickelt für RedBot v3+**  
**Keine externen Abhängigkeiten**
