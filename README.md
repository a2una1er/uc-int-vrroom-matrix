# HDFury VRRoom Integration für Unfolded Circle Remote Three

Python-Integration für den HDFury VRRoom HDMI-Matrix-Switch im Matrix-Mode.

## Features

- **TX0 Input** — Dropdown zur Auswahl des Eingangs für Ausgang TX0
- **TX1 Input** — Dropdown zur Auswahl des Eingangs für Ausgang TX1
- **VRRoom Misc** — Reboot und HotPlug-Befehle
- **Polling** — Automatische Statusaktualisierung (konfigurierbar, default 5s)
- **Benutzerdefinierte Eingangsnamen** — z.B. "PC", "PS5", "Switch" statt RX0–RX3

## Voraussetzungen

- Python 3.11 oder neuer
- HDFury VRRoom im lokalen Netzwerk (Matrix-Mode)
- Unfolded Circle Remote Three (Firmware mit Core API ≥ 0.22.0)

## Installation

### Extern auf dem PC (zum Entwickeln/Testen)

```bash
pip install -r requirements.txt
python src/driver.py
```

Der Driver announced sich per mDNS im Netzwerk. Die Remote findet ihn automatisch unter **Settings → Integrations → Add Integration**.

### Docker

```bash
docker run -d \
  --name uc-vrroom \
  --network host \
  -e UC_CONFIG_HOME=/data \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  -v vrroom-config:/data \
  python:3.11-slim \
  sh -c "pip install -r requirements.txt && python src/driver.py"
```

## Konfiguration

Beim Einrichten der Integration auf der Remote werden folgende Felder abgefragt:

| Feld | Beschreibung | Default |
|------|-------------|---------|
| Host | Hostname oder IP des VRRoom | `vrroom` |
| Name für RX0–RX3 | Anzeigenamen für die Eingänge (z.B. PC, PS5, Switch, Dock) | RX0–RX3 |
| Name für Copy-Mode | Anzeigename für den Copy-Modus | Copy |
| Polling-Intervall | Statusabfrage in ms (0 = deaktiviert) | 5000 |

Die Eingangsnamen erscheinen in den Dropdown-Listen der TX0/TX1 Select-Entities.

## Entities

| Entity | Typ | Beschreibung |
|--------|-----|-------------|
| TX0 Input | Select | Dropdown zur Eingangswahl für Ausgang TX0 |
| TX1 Input | Select | Dropdown zur Eingangswahl für Ausgang TX1 |
| VRRoom Misc | Remote | Befehle: REBOOT, HOTPLUG |

Die Select-Entities können auf der Startseite und in Activities verwendet werden.

## VRRoom HTTP API

| Endpunkt | Funktion |
|----------|----------|
| `GET /ssi/infopage.ssi` | Status abrufen (JSON) |
| `GET /cmd?insel={tx0}%20{tx1}` | Eingänge umschalten |
| `GET /cmd?reboot` | Gerät neu starten |
| `GET /cmd?hotplug=` | HotPlug-Event auslösen |

## Entwicklung

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Tests ausführen
pytest tests/ -v

# Property-Based Tests mit festem Seed
pytest tests/ -v --hypothesis-seed=0
```

## Projektstruktur

```
/
├── src/
│   ├── driver.py          # Einstiegspunkt, Event-Handler, Polling
│   ├── select_entity.py   # TX0/TX1 Select-Entities (Dropdowns)
│   ├── remote_entity.py   # Misc-Entity (REBOOT, HOTPLUG)
│   ├── http_client.py     # HTTP GET-Kommunikation mit VRRoom
│   ├── status_parser.py   # JSON-Parsing der VRRoom-Antwort
│   └── settings.py        # GlobalSettings (Host, Namen, Polling)
├── tests/                 # Unit- und Property-Based Tests
├── docs/                  # VERIFY.md
├── driver.json            # Driver-Metadaten und Setup-Schema
├── requirements.txt       # ucapi, aiohttp
├── requirements-dev.txt   # hypothesis, pytest
└── .github/workflows/     # GitHub Actions Build & Release
```

## Build & Release

Ein Git-Tag `v*` löst den GitHub Actions Workflow aus:
- Baut ein aarch64-Binary mit PyInstaller
- Erstellt ein `.tar.gz` für die Installation auf der Remote
- Erstellt einen GitHub Release Draft

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Lizenz

Mozilla Public License 2.0
