# Player Access Control - Modern Whitelist System

Ein modernes Whitelist-Management-System für RedBot mit interaktivem Dropdown-Menü.

## ✨ Features

- **Interaktives Dropdown-Menü** - Wähle Spieler aus einer Liste und whiteliste sie mit einem Klick
- **Automatische Rollenvergabe** - Spieler erhalten automatisch die Whitelist-Rolle
- **Modernes Embed Design** - Schöne, formatierte Embeds mit Thumbnails und Emojis
- **Admin-System** - Vergebe Admin-Rollen für den Zugriff auf den Cog
- **Action Logging** - Alle Aktionen werden protokolliert (optional)
- **Statistiken** - Detaillierte Statistiken über gewhitelistete Spieler
- **Suchfunktion** - Finde Spieler schnell in der Whitelist
- **Pagination** - Durchsuchbare Spielerlisten mit Seitennavigation
- **Export/Import** - Sichere und restore deine Whitelist-Daten
- **Cleanup-Funktion** - Entferne automatisch Spieler die den Server verlassen haben
- **Verifizierung** - Überprüfe den Whitelist-Status von Spielern

## 📋 Befehle

### Hauptbefehle
- `[p]pa menu` - Öffnet das Hauptmenü mit Dropdown
- `[p]pa setup` - Interaktiver Setup-Assistent
- `[p]pa setrole @Rolle` - Setzt die Whitelist-Rolle
- `[p]pa add <@Spieler>` - Fügt einen Spieler manuell hinzu
- `[p]pa remove <@Spieler>` - Entfernt einen Spieler
- `[p]pa list` - Zeigt alle gewhitelisteten Spieler
- `[p]pa stats` - Zeigt Statistiken
- `[p]pa search <Name>` - Sucht nach Spielern
- `[p]pa verify <@Spieler>` - Überprüft Whitelist-Status
- `[p]pa cleanup` - Entfernt verlassene Mitglieder
- `[p]pa export` - Exportiert Whitelist als JSON
- `[p]pa import` - Importiert Whitelist aus JSON
- `[p]pa history` - Zeigt letzte Aktionen

### Admin-Befehle
- `[p]pa addadmin @Rolle` - Fügt Admin-Rolle hinzu
- `[p]pa removeadmin @Rolle` - Entfernt Admin-Rolle
- `[p]pa admins` - Zeigt alle Admin-Rollen

## 🚀 Installation

1. **Installationspfad setzen:**
   ```
   [p]cog installpath /workspace/player_access
   ```

2. **Cog laden:**
   ```
   [p]load player_access
   ```

3. **Setup durchführen:**
   ```
   [p]pa setup
   ```

4. **Whitelist-Rolle setzen:**
   ```
   [p]pa setrole @DeineRolle
   ```

5. **(Optional) Admin-Rollen hinzufügen:**
   ```
   [p]pa addadmin @AdminRolle
   ```

6. **Fertig! Nutze das Menü:**
   ```
   [p]pa menu
   ```

## 🎮 Verwendung

### Spieler whitelisten

1. Öffne das Menü mit `[p]pa menu`
2. Wähle einen Spieler aus dem Dropdown
3. Der Spieler erhält automatisch die Whitelist-Rolle

### Spielerliste durchsuchen

1. Klicke im Menü auf "Spielerliste"
2. Nutze die Pfeil-Buttons zum Navigieren
3. Klicke "Zurück zum Menü" um zurückzukehren

### Statistiken anzeigen

- Klicke im Menü auf "Statistiken" ODER
- Nutze `[p]pa stats`

## 🔒 Berechtigungen

- **Owner** - Vollzugriff
- **Server Owner** - Vollzugriff
- **Administratoren** - Vollzugriff
- **Admin-Rollen** - Vollzugriff (müssen hinzugefügt werden)

## 📊 Datenstruktur

Gespeicherte Daten pro Spieler:
```json
{
  "id": 123456789,
  "name": "SpielerName",
  "added_by": 987654321,
  "added_at": "2024-01-01T12:00:00",
  "verified": true
}
```

## 🛠️ Konfiguration

### Gespeicherte Einstellungen (pro Server):
- `whitelist_role` - Die Rolle die Spieler erhalten
- `admin_roles` - Liste der Admin-Rollen
- `whitelisted_players` - Alle gewhitelisteten Spieler
- `log_channel` - Optionaler Log-Kanal
- `auto_cleanup` - Automatische Bereinigung
- `verification_required` - Verifizierung erforderlich
- `max_whitelist_size` - Maximale Größe

## 💡 Tipps

- Stelle sicher, dass die Whitelist-Rolle unter deiner höchsten Rolle liegt
- Füge mehrere Admin-Rollen für bessere Zugriffskontrolle hinzu
- Richte einen Log-Kanal ein für bessere Nachverfolgbarkeit
- Exportiere regelmäßig deine Whitelist als Backup

## 📝 Changelog

### Version 2.0
- ✅ Komplettes Redesign des Codes
- ✅ Modernes Dropdown-Menü
- ✅ Verbesserte Embed-Darstellung
- ✅ Pagination für Spielerlisten
- ✅ Export/Import-Funktionalität
- ✅ Cleanup-Funktion
- ✅ Erweiterte Statistiken
- ✅ Suchfunktion
- ✅ Action History

## ⚠️ Hinweise

- Der Cog speichert alle Daten lokal über RedBot's Config-System
- Bei Server-Wechsel des Bots bleiben die Daten erhalten
- Löschen des Cogs löscht alle gespeicherten Daten

## 🆘 Support

Bei Problemen:
1. Überprüfe die Bot-Berechtigungen
2. Stelle sicher, dass die Rolle korrekt gesetzt ist
3. Prüfe die Logs mit `[p]pa history`
4. Melde Bugs dem Entwickler

---

**Entwickelt für RedBot v3+**
