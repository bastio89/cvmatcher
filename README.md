# CV Matcher API

Semantisches Matching zwischen CVs und Stellenbeschreibungen — powered by lokaler KI (Ollama) und einer Vektordatenbank (Qdrant).

## Wie es funktioniert

1. CVs und Stellenbeschreibungen werden als PDF hochgeladen
2. Text wird extrahiert — bei Scan-PDFs automatisch via OCR (Tesseract)
3. Der Text wird in Vektoren (Embeddings) umgewandelt und in Qdrant gespeichert
4. Beim Matching wird per Kosinus-Ähnlichkeit die semantische Nähe berechnet
5. Ein lokales LLM analysiert die Top-Treffer und erstellt ein strukturiertes Ranking

```
PDF Upload → Text-Extraktion (PyMuPDF)
                 ↓ zu wenig Text?
             OCR-Fallback (Tesseract, DE+EN)
                 ↓
             Embedding (nomic-embed-text) → Qdrant
                                                ↓
Match-Request → Vektor-Suche → LLM-Analyse (llama3.2) → Ranking-Response
```

| PDF-Typ | Unterstützt | Methode |
|---|---|---|
| Text-PDF (Word/InDesign-Export) | ✓ | Direkte Extraktion via PyMuPDF |
| Scan-PDF (eingescannte Dokumente) | ✓ | Automatischer OCR-Fallback via Tesseract |
| Passwortgeschütztes PDF | ✗ | Nicht unterstützt |

---

## Schnellstart

```bash
git clone https://github.com/bastio89/cvmatcher.git
cd cvmatcher
```

---

## Option A — Docker (empfohlen für Server)

Alle Dienste (Qdrant, Ollama, API) laufen im Container. Kein Python-Setup nötig.

**Voraussetzungen:** Docker mit Docker Compose

### 1. Starten

```bash
docker compose up -d --build
```

Das startet automatisch:
- **Qdrant** auf Port `6333`
- **Ollama** auf Port `11434`
- **API** auf Port `8000`

Qdrant und Ollama sind intern über Docker-Netzwerk verbunden (`QDRANT_HOST=qdrant`, `OLLAMA_HOST=http://ollama:11434`) — keine manuelle Konfiguration nötig.

### 2. KI-Modelle laden (einmalig, ~3 GB)

```bash
# Warten bis Ollama läuft (ca. 10 Sekunden), dann:
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.2
```

> Dieser Schritt kann je nach Internetverbindung 5–15 Minuten dauern. Modelle werden dauerhaft in einem Docker-Volume gespeichert.

### 3. Prüfen

```bash
# Status aller Dienste
docker compose ps

# API-Health
curl http://localhost:8000/health

# Qdrant + Ollama gleichzeitig prüfen
curl http://localhost:8000/api/v1/health/services
```

**Demo-UI** ist unter `http://<server-ip>:8000` erreichbar — direkt im Browser.

### Dienste stoppen / neu starten

```bash
docker compose down          # stoppen (Daten bleiben im Volume)
docker compose down -v       # stoppen + alle Daten löschen
docker compose restart api   # nur API neu starten (nach Code-Änderungen)
docker compose up -d --build # neu bauen und starten
```

### GPU-Support (NVIDIA)

Im `docker-compose.yml` den auskommentierten Block unter `ollama` einkommentieren:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

---

## Option B — Lokal (Entwicklung)

Qdrant und Ollama laufen via Docker, die API läuft direkt auf dem Rechner.

**Voraussetzungen:** Docker, Python 3.12+

### 1. Infrastruktur starten

```bash
docker compose up -d qdrant ollama
```

### 2. KI-Modelle laden

```bash
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.2
```

### 3. Tesseract installieren (für OCR)

```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu / Debian
sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng

# Windows: Installer unter https://github.com/UB-Mannheim/tesseract/wiki
# Nach der Installation: Pfad zu tesseract.exe in PATH eintragen
```

### 4. Python-Abhängigkeiten

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Konfiguration

```bash
cp .env.example .env
# .env bei Bedarf anpassen (Standard-Werte funktionieren für lokale Docker-Dienste)
```

### 6. API starten

```bash
# Nur lokaler Zugriff
uvicorn app.main:app --reload

# Zugriff von anderen Geräten im Netzwerk (z.B. zum Testen vom Handy)
uvicorn app.main:app --host 0.0.0.0 --reload
```

Die API läuft auf **http://localhost:8000**

---

## Verbindungseinstellungen anpassen

Laufen Qdrant oder Ollama auf einem anderen Host (z.B. separater Server), gibt es zwei Wege:

### Via Demo-UI (empfohlen)

`http://localhost:8000` → Zahnrad-Icon (⚙) unten links in der Sidebar → Verbindungseinstellungen → Speichern.

Die Einstellungen werden in `runtime_settings.json` gespeichert und beim nächsten Start automatisch geladen.

### Via API

```bash
# Aktuelle Einstellungen abrufen
curl http://localhost:8000/api/v1/settings

# Einstellungen ändern
curl -X PUT http://localhost:8000/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{
    "qdrant_host": "192.168.1.100",
    "qdrant_port": 6333,
    "ollama_host": "http://192.168.1.100:11434"
  }'

# Konnektivität testen
curl http://localhost:8000/api/v1/health/services
```

### Via .env (dauerhaft, vor dem Start)

```env
QDRANT_HOST=192.168.1.100
QDRANT_PORT=6333
OLLAMA_HOST=http://192.168.1.100:11434
```

---

## Endpunkte

| URL | Beschreibung |
|---|---|
| `http://localhost:8000` | **Demo-UI** — alle Funktionen im Browser |
| `http://localhost:8000/docs` | Swagger UI — Endpunkte interaktiv testen |
| `http://localhost:8000/redoc` | ReDoc — API-Dokumentation |
| `http://localhost:8000/openapi.yaml` | OpenAPI-Spec als YAML |
| `http://localhost:8000/health` | API-Status |
| `http://localhost:8000/api/v1/health/services` | Qdrant + Ollama Konnektivität |
| `http://localhost:8000/api/v1/settings` | Verbindungseinstellungen (GET/PUT) |

---

## Benutzung (API)

### CVs hochladen

```bash
curl -X POST http://localhost:8000/api/v1/cvs/batch \
  -F "files=@cv_max_mustermann.pdf" \
  -F "files=@cv_anna_schmidt.pdf"
```

**Antwort:**
```json
{
  "documents": [
    { "id": "a1b2c3d4-...", "type": "cv", "filename": "cv_max_mustermann.pdf", "text_length": 3240, "ocr_used": false, "status": "indexed" },
    { "id": "e5f6g7h8-...", "type": "cv", "filename": "cv_anna_schmidt.pdf",   "text_length": 2890, "ocr_used": true,  "status": "indexed" }
  ],
  "total": 2,
  "failed": []
}
```

`ocr_used: true` bedeutet, dass mindestens eine Seite per Tesseract erkannt wurde.

### Stellenbeschreibungen hochladen

```bash
curl -X POST http://localhost:8000/api/v1/jobs/batch \
  -F "files=@stelle_backend_entwickler.pdf"
```

### Matching starten

**Job → beste Kandidaten (CVs ranken):**

```bash
curl -X POST http://localhost:8000/api/v1/match \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "<job-id>",
    "document_type": "job",
    "top_k": 5,
    "include_analysis": true,
    "scoring": { "vector": 0.3, "llm": 0.7 }
  }'
```

**CV → passende Stellen:**

```bash
curl -X POST http://localhost:8000/api/v1/match \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "<cv-id>",
    "document_type": "cv",
    "top_k": 10,
    "include_analysis": true,
    "scoring": { "vector": 0.3, "llm": 0.7 }
  }'
```

**Nur Vektor-Score (ohne LLM, sehr schnell):**

```bash
curl -X POST http://localhost:8000/api/v1/match \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "<job-id>",
    "document_type": "job",
    "top_k": 20,
    "include_analysis": false,
    "scoring": { "vector": 1.0, "llm": 0.0 }
  }'
```

**Antwort:**
```json
{
  "match_id": "uuid",
  "query_document_id": "<job-id>",
  "query_document_type": "job",
  "target_type": "cv",
  "scoring": { "vector": 0.3, "llm": 0.7 },
  "total_candidates": 5,
  "results": [
    {
      "rank": 1,
      "document_id": "a1b2c3d4-...",
      "filename": "cv_max_mustermann.pdf",
      "similarity_score": 0.9124,
      "final_score": 0.8787,
      "analysis": {
        "overall_score": 87,
        "overall_label": "Excellent",
        "summary": "Max Mustermann bringt 5 Jahre Python-Erfahrung mit...",
        "skills": {
          "matching": ["Python", "FastAPI", "PostgreSQL"],
          "missing": ["Kubernetes"],
          "bonus": ["Rust", "Open-Source-Erfahrung"]
        },
        "strengths": ["Starke Backend-Erfahrung"],
        "gaps": ["Keine Erfahrung mit Container-Orchestrierung"]
      }
    }
  ]
}
```

`final_score = vector × similarity_score + llm × (overall_score / 100)`

### Alle Dokumente auflisten

```bash
curl "http://localhost:8000/api/v1/documents?limit=20"
curl "http://localhost:8000/api/v1/documents?type=cv&limit=20"
curl "http://localhost:8000/api/v1/documents?cursor=<next_cursor>"
```

### Dokument abrufen / löschen

```bash
curl http://localhost:8000/api/v1/documents/<id>
curl -X DELETE http://localhost:8000/api/v1/documents/<id>
```

### Batch-Matching

```bash
curl -X POST http://localhost:8000/api/v1/match/batch \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": ["<job-id-1>", "<job-id-2>"],
    "document_type": "job",
    "top_k": 5,
    "include_analysis": true,
    "scoring": { "vector": 0.3, "llm": 0.7 }
  }'
```

---

## Parameter-Referenz

### `POST /api/v1/match` und `POST /api/v1/match/batch`

| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `document_id` / `document_ids` | string / string[] | — | Quell-Dokument(e) (max. 500 beim Batch) |
| `document_type` | `"cv"` oder `"job"` | — | Typ der Quell-Dokumente |
| `top_k` | integer | `10` / `5` | Top-Treffer pro Dokument (max. 100) |
| `include_analysis` | boolean | `true` | LLM-Analyse pro Treffer (langsamer, aber informativ) |
| `scoring.vector` | float | `0.3` | Gewicht der Vektor-Ähnlichkeit (0.0–1.0) |
| `scoring.llm` | float | `0.7` | Gewicht des LLM-Scores (0.0–1.0) |

> `scoring.vector + scoring.llm` muss genau `1.0` ergeben.  
> Bei `include_analysis: false` wird `scoring.llm` ignoriert.

### `GET /api/v1/documents`

| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `type` | `"cv"` oder `"job"` | — | Filter nach Typ (optional) |
| `limit` | integer | `20` | Einträge pro Seite (max. 100) |
| `cursor` | string | — | Cursor aus vorheriger Antwort |

---

## Auf Cloud-KI umstellen (Anthropic/Claude)

```bash
pip install anthropic voyageai
```

`.env` anpassen:

```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_EMBEDDING_MODEL=voyage-3
ANTHROPIC_LLM_MODEL=claude-sonnet-4-6
```

> **Achtung:** Beim Wechsel des Embedding-Modells müssen alle Dokumente neu hochgeladen werden (Ollama: 768 Dim, Voyage-3: 1024 Dim). Qdrant-Collection vorher leeren:
> ```bash
> curl -X DELETE http://localhost:6333/collections/documents
> ```

---

## Projektstruktur

```
.
├── app/
│   ├── main.py                   # FastAPI-App, Startup, statische UI
│   ├── config.py                 # Konfiguration via .env
│   ├── dependencies.py           # Dependency Injection (lru_cache Singletons)
│   ├── models/
│   │   └── schemas.py            # Request/Response-Datenmodelle (Pydantic v2)
│   ├── providers/
│   │   ├── base.py               # Abstrakte Provider-Schnittstelle
│   │   ├── ollama_provider.py    # Lokale KI (Standard)
│   │   └── anthropic_provider.py # Cloud-KI (optional)
│   ├── routers/
│   │   ├── documents.py          # Upload- und Verwaltungs-Endpunkte
│   │   ├── matching.py           # Match- und Batch-Endpunkte
│   │   └── settings.py           # Verbindungseinstellungen + Health-Services
│   ├── services/
│   │   ├── pdf_extractor.py      # PDF → Text (mit OCR-Fallback)
│   │   ├── vector_store.py       # Qdrant-Wrapper
│   │   └── matcher.py            # Matching-Logik + Re-Ranking
│   └── static/
│       └── index.html            # Demo-UI (Alpine.js SPA)
├── docker-compose.yml            # Qdrant + Ollama + API
├── Dockerfile                    # API-Container (inkl. Tesseract)
├── requirements.txt
├── .env.example                  # Konfigurationsvorlage
└── runtime_settings.json         # Laufzeit-Einstellungen (auto-generiert, nicht in Git)
```

---

## Fehlerbehebung

**API nicht von außen erreichbar:**
```bash
# Lokal: --host 0.0.0.0 verwenden
uvicorn app.main:app --host 0.0.0.0 --reload
# Docker: ist bereits mit 0.0.0.0 konfiguriert
# Firewall: Port 8000 freigeben
```

**Qdrant oder Ollama nicht erreichbar:**
```bash
# Status im Browser prüfen:
# http://localhost:8000 → Sidebar zeigt Qdrant/Ollama-Status (grün/rot)

# Oder per API:
curl http://localhost:8000/api/v1/health/services

# Logs prüfen:
docker compose logs qdrant
docker compose logs ollama

# Direkt testen:
curl http://localhost:6333/health
curl http://localhost:11434/api/tags
```

**Modell nicht gefunden (`model not found`):**
```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.2
```

**OCR funktioniert nicht (`tesseract not found`):**
```bash
brew install tesseract tesseract-lang   # macOS
which tesseract && tesseract --version  # Prüfen
```

**OCR-Ergebnis schlecht:**
- Scan-Qualität unter 150 DPI → schlechte Erkennungsrate, 300 DPI empfohlen
- Die OCR-Auflösung ist in `app/services/pdf_extractor.py` via `_OCR_DPI = 300` konfigurierbar

**Verbindungseinstellungen zurücksetzen:**
```bash
# runtime_settings.json löschen → .env-Defaults werden wieder verwendet
rm runtime_settings.json
```
