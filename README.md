# CV Matcher API

Semantisches Matching zwischen CVs und Stellenbeschreibungen — powered by lokaler KI (Ollama) und einer Vektordatenbank (Qdrant).

## Wie es funktioniert

1. CVs und Stellenbeschreibungen werden als PDF hochgeladen
2. Text wird extrahiert — bei Scan-PDFs (Bilder ohne Text-Layer) automatisch via OCR (Tesseract)
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

### PDF-Unterstützung

| PDF-Typ | Unterstützt | Methode |
|---|---|---|
| Text-PDF (normales Word/InDesign-Export) | ✓ | Direkte Extraktion via PyMuPDF |
| Scan-PDF (eingescannte Dokumente) | ✓ | Automatischer OCR-Fallback via Tesseract |
| Bild-PDF mit eingebettetem Text | ✓ | OCR-Fallback |
| Passwortgeschütztes PDF | ✗ | Nicht unterstützt |

Die Response enthält ein Feld `ocr_used: true/false` das anzeigt, ob OCR für das Dokument verwendet wurde.

---

## Voraussetzungen

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (läuft Qdrant + Ollama)
- Python 3.12+
- ca. 5 GB freier Speicherplatz (für die KI-Modelle)

---

## Setup (Erstinstallation)

### Schritt 1 — Repository vorbereiten

```bash
cd "Schnittstelle CV Mapper"
cp .env.example .env
```

### Schritt 2 — Docker-Dienste starten

```bash
docker compose up -d qdrant ollama
```

Warten bis beide Dienste laufen (ca. 10–20 Sekunden):

```bash
docker compose ps
```

### Schritt 3 — KI-Modelle laden (einmalig, ~3 GB)

```bash
# Embedding-Modell (768 Dimensionen, schnell)
docker exec -it $(docker compose ps -q ollama) ollama pull nomic-embed-text

# LLM für Analyse (ca. 2 GB)
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.2
```

> **Hinweis:** Dieser Schritt kann je nach Internetverbindung 5–15 Minuten dauern. Modelle werden dauerhaft gespeichert und müssen nur einmal geladen werden.

### Schritt 4 — Tesseract installieren (für OCR-Support)

Tesseract muss als Systemprogramm vorhanden sein — wird beim Docker-Build automatisch eingebettet, für lokale Entwicklung manuell installieren:

```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu / Debian
sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng

# Windows
# Installer: https://github.com/UB-Mannheim/tesseract/wiki
# Nach der Installation: Pfad zu tesseract.exe in PATH eintragen
```

### Schritt 5 — Python-Abhängigkeiten installieren

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Schritt 6 — API starten

```bash
uvicorn app.main:app --reload
```

Die API läuft jetzt auf **http://localhost:8000**

| URL | Beschreibung |
|---|---|
| http://localhost:8000/docs | Interaktive Swagger UI — Endpunkte direkt ausprobieren |
| http://localhost:8000/redoc | ReDoc — saubere, lesbare Dokumentationsansicht |
| http://localhost:8000/openapi.json | OpenAPI-Spec als JSON (maschinenlesbar) |
| http://localhost:8000/openapi.yaml | OpenAPI-Spec als YAML (maschinenlesbar) |

---

## Benutzung

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

Speichere die `id` — du brauchst sie für das Matching. `ocr_used: true` bedeutet, dass mindestens eine Seite per Tesseract erkannt wurde.

---

### Stellenbeschreibungen hochladen

```bash
curl -X POST http://localhost:8000/api/v1/jobs/batch \
  -F "files=@stelle_backend_entwickler.pdf" \
  -F "files=@stelle_data_scientist.pdf"
```

---

### Matching starten

#### Option A: Job → beste Kandidaten (CVs ranken)

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

#### Option B: CV → passende Stellen

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

#### Option C: Nur Vektor-Score (ohne LLM, sehr schnell)

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
        "summary": "Max Mustermann bringt 5 Jahre Python-Erfahrung mit und deckt den Großteil der geforderten Skills ab.",
        "skills": {
          "matching": ["Python", "FastAPI", "PostgreSQL"],
          "missing": ["Kubernetes"],
          "bonus": ["Rust", "Open-Source-Erfahrung"]
        },
        "strengths": ["Starke Backend-Erfahrung", "Nachgewiesene API-Projekte"],
        "gaps": ["Keine Erfahrung mit Container-Orchestrierung"]
      }
    }
  ]
}
```

`final_score` = `vector * similarity_score + llm * (overall_score / 100)` — das ist die Basis des Rankings.

### Alle Dokumente auflisten

```bash
# Alle Dokumente (erste Seite)
curl "http://localhost:8000/api/v1/documents?limit=20"

# Nur CVs
curl "http://localhost:8000/api/v1/documents?type=cv&limit=20"

# Nächste Seite (cursor aus vorheriger Antwort)
curl "http://localhost:8000/api/v1/documents?cursor=<next_cursor>"
```

**Antwort:**
```json
{
  "items": [
    { "id": "a1b2c3d4-...", "type": "cv", "filename": "cv_max_mustermann.pdf", "text_length": 3240 },
    { "id": "e5f6g7h8-...", "type": "job", "filename": "stelle_backend.pdf",   "text_length": 1820 }
  ],
  "total": 42,
  "limit": 20,
  "next_cursor": "c3d4e5f6-..."
}
```

`next_cursor` ist `null` wenn keine weitere Seite existiert.

---

### Dokument abrufen

```bash
curl http://localhost:8000/api/v1/documents/<document-id>
```

**Antwort:**
```json
{
  "id": "a1b2c3d4-...",
  "type": "cv",
  "filename": "cv_max_mustermann.pdf",
  "text": "Max Mustermann\nSoftware Engineer...",
  "text_length": 3240
}
```

Nützlich um zu prüfen, ob Text und OCR korrekt extrahiert wurden.

---

### Dokument löschen

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/<document-id>
```

**Antwort:**
```json
{ "id": "a1b2c3d4-...", "deleted": true }
```

---

### Batch-Matching (mehrere Dokumente gleichzeitig)

```bash
curl -X POST http://localhost:8000/api/v1/match/batch \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": ["<job-id-1>", "<job-id-2>", "<job-id-3>"],
    "document_type": "job",
    "top_k": 5,
    "include_analysis": true
  }'
```

**Antwort:**
```json
{
  "batch_id": "uuid",
  "document_type": "job",
  "total_sources": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "document_id": "<job-id-1>",
      "filename": "stelle_backend.pdf",
      "status": "ok",
      "match": {
        "match_id": "uuid",
        "results": [ { "rank": 1, "filename": "cv_max_mustermann.pdf", "similarity_score": 0.91, "..." } ]
      }
    },
    { "document_id": "<job-id-2>", "filename": "stelle_data.pdf", "status": "ok", "match": { "..." } },
    { "document_id": "<job-id-3>", "filename": "",                 "status": "error", "error": "Dokument nicht gefunden" }
  ]
}
```

Einzelne Fehler (`status: "error"`) brechen den Rest des Batches nicht ab.

---

## Parameter-Referenz

### `POST /api/v1/match`

| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `document_id` | string | — | ID des Quell-Dokuments (aus dem Upload) |
| `document_type` | `"cv"` oder `"job"` | — | Typ des Quell-Dokuments |
| `top_k` | integer | `10` | Anzahl der zurückgegebenen Treffer (max. 100) |
| `include_analysis` | boolean | `true` | LLM-Detailanalyse pro Treffer (langsamer, aber informativ) |

> **Tipp:** `include_analysis: false` ist deutlich schneller — sinnvoll wenn du nur einen schnellen Score-Überblick brauchst.

### `GET /api/v1/documents`

| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `type` | `"cv"` oder `"job"` | — | Filter nach Dokumenttyp (optional) |
| `limit` | integer | `20` | Einträge pro Seite (max. 100) |
| `cursor` | string | — | Cursor aus vorheriger Antwort für nächste Seite |

### `POST /api/v1/match` und `POST /api/v1/match/batch`

| Parameter | Typ | Standard | Beschreibung |
|---|---|---|---|
| `document_id` / `document_ids` | string / string[] | — | Quell-Dokument(e) |
| `document_type` | `"cv"` oder `"job"` | — | Typ der Quell-Dokumente |
| `top_k` | integer | `10` / `5` | Top-Treffer (max. 100) |
| `include_analysis` | boolean | `true` | LLM-Analyse pro Treffer |
| `scoring.vector` | float | `0.3` | Gewicht der Vektor-Ähnlichkeit (0.0–1.0) |
| `scoring.llm` | float | `0.7` | Gewicht des LLM-Scores (0.0–1.0) |

> `scoring.vector + scoring.llm` muss genau `1.0` ergeben.
> Bei `include_analysis: false` wird `scoring.llm` ignoriert — Ranking basiert rein auf `similarity_score`.

---

## Täglicher Betrieb

```bash
# Dienste starten
docker compose up -d qdrant ollama
source .venv/bin/activate
uvicorn app.main:app --reload

# Dienste stoppen
docker compose down

# Status prüfen
curl http://localhost:8000/health
```

---

## Auf Cloud-KI umstellen (Anthropic/Claude)

Wenn du später von lokaler KI auf Claude wechseln möchtest:

### 1. Zusätzliche Pakete installieren

```bash
pip install anthropic voyageai
```

### 2. `.env` anpassen

```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_EMBEDDING_MODEL=voyage-3
ANTHROPIC_LLM_MODEL=claude-sonnet-4-6
```

### 3. API neu starten

```bash
uvicorn app.main:app --reload
```

Der gesamte restliche Code bleibt unverändert.

> **Achtung:** Beim Wechsel des Embedding-Modells müssen alle Dokumente neu hochgeladen werden, da die Vektoren inkompatible Dimensionen haben (Ollama nomic-embed-text: 768 Dim, Voyage-3: 1024 Dim). Qdrant-Collection vorher leeren:
> ```bash
> curl -X DELETE http://localhost:6333/collections/documents
> ```

---

## Projektstruktur

```
.
├── app/
│   ├── main.py               # FastAPI-App & Startup
│   ├── config.py             # Konfiguration via .env
│   ├── dependencies.py       # Dependency Injection
│   ├── models/
│   │   └── schemas.py        # Request/Response-Datenmodelle
│   ├── providers/
│   │   ├── base.py           # Abstrakte Provider-Schnittstelle
│   │   ├── ollama_provider.py    # Lokale KI (Standard)
│   │   └── anthropic_provider.py # Cloud-KI (optional)
│   ├── routers/
│   │   ├── documents.py      # Upload-Endpunkte
│   │   └── matching.py       # Match-Endpunkt
│   └── services/
│       ├── pdf_extractor.py  # PDF → Text
│       ├── vector_store.py   # Qdrant-Wrapper
│       └── matcher.py        # Matching-Logik + Re-Ranking
├── docker-compose.yml        # Qdrant + Ollama
├── requirements.txt
├── .env                      # Lokale Konfiguration (nicht in Git)
└── .env.example              # Vorlage
```

---

## Fehlerbehebung

**Ollama antwortet nicht:**
```bash
docker compose logs ollama
# Prüfen ob Port 11434 frei ist
lsof -i :11434
```

**Qdrant nicht erreichbar:**
```bash
docker compose logs qdrant
curl http://localhost:6333/health
```

**Modell nicht gefunden (`model not found`):**
```bash
docker exec -it $(docker compose ps -q ollama) ollama list
# Falls nicht vorhanden: erneut pullen
docker exec -it $(docker compose ps -q ollama) ollama pull nomic-embed-text
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.2
```

**OCR funktioniert nicht / `tesseract not found`:**
```bash
# macOS
brew install tesseract tesseract-lang
# Pfad prüfen
which tesseract
tesseract --version
```

**OCR-Ergebnis schlecht (falsch erkannte Zeichen):**
- Scan-Qualität unter 150 DPI → schlechte Erkennungsrate, 300 DPI empfohlen
- Schräg eingescannte Dokumente → manuelle Begradigung vor dem Upload
- Die OCR-Auflösung ist in `pdf_extractor.py` via `_OCR_DPI = 300` konfigurierbar

**PDF-Extraktion schlägt fehl:**
Passwortgeschützte PDFs werden nicht unterstützt — Passwort vorher entfernen.
