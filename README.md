# HDFury VRRoom Integration für Unfolded Circle Remote Three

Python-Integration für den HDFury VRRoom HDMI-Matrix-Switch im Matrix-Mode.

## Voraussetzungen

- Python 3.11 oder neuer
- HDFury VRRoom im lokalen Netzwerk (Matrix-Mode)
- Unfolded Circle Remote Three

## Installation

### Option 1: Direkt auf der Remote Three

1. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

2. Driver starten:
   ```bash
   python src/driver.py
   ```

### Option 2: Externer Host (Docker)

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

Bei der Einrichtung in der Remote Three Web-Oberfläche:

1. Gehe zu **Settings → Integrations → Add Integration**
2. Wähle **HDFury VRRoom**
3. Gib den **Hostname oder die IP-Adresse** des VRRoom ein (Standard: `vrroom`)

## Unterstützte Befehle

| Befehl | Beschreibung |
|--------|-------------|
| `SELECT_TX0_RX0` | Eingang RX0 auf Ausgang TX0 |
| `SELECT_TX0_RX1` | Eingang RX1 auf Ausgang TX0 |
| `SELECT_TX0_RX2` | Eingang RX2 auf Ausgang TX0 |
| `SELECT_TX0_RX3` | Eingang RX3 auf Ausgang TX0 |
| `SELECT_TX0_COPY` | Copy-Mode auf TX0 (spiegelt TX1) |
| `SELECT_TX1_RX0` | Eingang RX0 auf Ausgang TX1 |
| `SELECT_TX1_RX1` | Eingang RX1 auf Ausgang TX1 |
| `SELECT_TX1_RX2` | Eingang RX2 auf Ausgang TX1 |
| `SELECT_TX1_RX3` | Eingang RX3 auf Ausgang TX1 |
| `SELECT_TX1_COPY` | Copy-Mode auf TX1 (spiegelt TX0) |
| `REBOOT` | Gerät neu starten |
| `HOTPLUG` | HotPlug-Event auslösen ⚠️ Endpunkt noch zu verifizieren |

## Entwicklung

```bash
# Abhängigkeiten installieren
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
├── src/               # Python-Quellcode
│   ├── driver.py      # Einstiegspunkt
│   ├── settings.py    # GlobalSettings
│   ├── http_client.py # HTTP-Kommunikation
│   ├── status_parser.py # JSON-Parsing
│   └── remote_entity.py # ucapi Remote-Entity
├── tests/             # Testdateien
├── docs/              # Weitere Dokumentation (VERIFY.md, ...)
├── driver.json        # Driver-Metadaten
├── README.md
├── requirements.txt
└── requirements-dev.txt
```

## Lizenz

Mozilla Public License 2.0
