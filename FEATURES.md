# Feature-Übersicht: CV Matcher API

> Stand: Version 1.0.0

---

## Umgesetzte Features

### Dokument-Upload & Indexierung

- **Batch-Upload von CVs** (`POST /api/v1/cvs/batch`)
  - Mehrere PDFs in einem Request hochladbar
  - Jedes Dokument erhält eine eindeutige UUID zur späteren Referenzierung
  - Antwort enthält pro Datei: ID, Zeichenanzahl, OCR-Status, Indexierungsstatus

- **Batch-Upload von Stellenbeschreibungen** (`POST /api/v1/jobs/batch`)
  - Identischer Ablauf wie CV-Upload
  - Dokumente werden intern als `type: job` markiert und getrennt durchsuchbar gehalten

- **Dokument abrufen** (`GET /api/v1/documents/{id}`)
  - Gibt Metadaten (ID, Typ, Dateiname) und den vollständig extrahierten Text zurück
  - Nützlich zur Prüfung ob OCR sauber funktioniert hat

- **Dokument löschen** (`DELETE /api/v1/documents/{id}`)
  - Entfernt ein einzelnes Dokument dauerhaft aus dem Vektorindex
  - 404 wenn die ID nicht existiert

- **Alle Dokumente auflisten** (`GET /api/v1/documents`)
  - Cursor-basierte Paginierung (bis 100 Einträge pro Seite)
  - Optionaler Filter nach Typ (`cv` oder `job`)
  - Antwort enthält Gesamtanzahl (`total`) und `next_cursor` für die nächste Seite

- **Persistente Indexierung**
  - Alle Dokumente werden dauerhaft in Qdrant gespeichert
  - Neustart der API verliert keine Daten (Volume-persistiert via Docker)
  - Dokumente können beliebig oft erneut gegen neue Uploads gematcht werden

---

### PDF-Verarbeitung

- **Direkte Text-Extraktion** via PyMuPDF
  - Schnell und präzise für alle standard Text-PDFs (Word-Export, InDesign, LaTeX)
  - Behält Zeilenstruktur und Absatzlogik bei

- **Automatischer OCR-Fallback** via Tesseract
  - Wird pro Seite ausgelöst wenn weniger als 50 Zeichen extrahiert werden
  - Unterstützte Sprachen: **Deutsch + Englisch** gleichzeitig
  - Rendering-Auflösung: 300 DPI (konfigurierbar)
  - Transparenz: Response-Feld `ocr_used: true/false` zeigt an ob OCR verwendet wurde

- **Unterstützte PDF-Typen**

  | PDF-Typ | Unterstützt |
  |---|:---:|
  | Standard Text-PDF | ✅ |
  | Eingescanntes Dokument (Scan-PDF) | ✅ |
  | Bild-PDF mit Text-Layer | ✅ |
  | Gemischte PDFs (teils Text, teils Scan) | ✅ |
  | Passwortgeschütztes PDF | ❌ |

---

### Semantisches Matching

- **Zwei Matching-Modi**
  - `cv → jobs`: Ein CV als Eingabe → findet die passendsten Stellenbeschreibungen
  - `job → cvs`: Eine Stelle als Eingabe → findet die passendsten Kandidaten (Ranking)

- **Batch-Matching** (`POST /api/v1/match/batch`)
  - Mehrere Quell-Dokumente (bis zu 500) in einem einzigen Request matchen
  - Jedes Dokument erhält ein eigenes vollständiges Ranking-Ergebnis
  - Fehlgeschlagene Einzeldokumente werden als `status: "error"` markiert, der Rest wird trotzdem verarbeitet
  - Typische Anwendungsfälle: alle eingegangenen Bewerbungen auf einmal gegen eine Stelle prüfen, oder einen Kandidaten gegen alle offenen Stellen testen

- **Vektorbasierte Ähnlichkeitssuche**
  - Kosinus-Ähnlichkeit über Qdrant — semantisch, nicht nur keyword-basiert
  - Erkennt inhaltliche Übereinstimmungen auch wenn unterschiedliche Begriffe verwendet werden (z. B. „Softwareentwickler" ↔ „Software Engineer")
  - Konfigurierbare Trefferanzahl (`top_k`, 1–100)

- **LLM-Detailanalyse** (optional, `include_analysis: true`)
  - Pro Treffer: strukturierte Analyse durch das lokale LLM
  - Re-Ranking: nach gewichtetem `final_score` neu sortiert

- **Konfigurierbare Score-Gewichtung** (`scoring`)
  - Feld `scoring: { vector, llm }` in jedem Match-Request
  - `vector + llm` muss 1.0 ergeben (Validierung auf API-Ebene)
  - Standard: 30 % Vektor-Ähnlichkeit + 70 % LLM-Score
  - Vektor-only-Modus: `{ vector: 1.0, llm: 0.0 }` (oder `include_analysis: false`)
  - LLM-only-Modus: `{ vector: 0.0, llm: 1.0 }`
  - Gilt sowohl für `/match` als auch `/match/batch`

- **Strukturiertes Ranking-Ergebnis** pro Treffer:
  - `rank` — Position im Ranking
  - `similarity_score` — Kosinus-Ähnlichkeit (0.0–1.0)
  - `final_score` — Gewichteter Gesamtscore, Basis des Rankings (0.0–1.0)
  - `overall_score` — LLM-Bewertung (0–100)
  - `overall_label` — Excellent / Good / Moderate / Poor
  - `summary` — 2–3 Sätze Gesamteinschätzung
  - `skills.matching` — gemeinsame Qualifikationen
  - `skills.missing` — geforderte Skills die fehlen
  - `skills.bonus` — Zusatzqualifikationen im CV
  - `strengths` — konkrete Stärken der Passung
  - `gaps` — konkrete Lücken

---

### KI-Provider-System

- **Lokaler Betrieb via Ollama** (Standard, ohne externe Abhängigkeiten)
  - Embedding-Modell: `nomic-embed-text` (768 Dimensionen)
  - LLM für Analyse: `llama3.2`
  - Vollständig offline-fähig, keine API-Kosten

- **Provider-Pattern** (erweiterbar ohne Code-Änderungen)
  - Abstrakte Basis-Schnittstelle in `providers/base.py`
  - Neuer Provider = neue Klasse, Umschalten via `.env`

- **Anthropic/Claude-Provider vorbereitet** (noch nicht aktiv)
  - Claude für LLM-Analyse
  - Voyage AI für Embeddings (1024 Dimensionen)
  - Aktivierbar via `AI_PROVIDER=anthropic` + API-Key

---

### API & Infrastruktur

- **REST-API** via FastAPI
  - Vollständig async
  - Automatische Request-Validierung via Pydantic
  - Strukturierte Fehlerantworten mit HTTP-Statuscodes

- **OpenAPI-Dokumentation** (automatisch generiert)
  - Swagger UI: `/docs` — interaktiv, direkt ausprobierbar
  - ReDoc: `/redoc` — sauber, lesbar, druckbar
  - Maschinenlesbar: `/openapi.json` und `/openapi.yaml`
  - Alle Endpunkte mit Beispiel-Payloads und Feldbeschreibungen

- **Health-Check** (`GET /health`)
  - Gibt API-Status und aktiven KI-Provider zurück

- **Docker-Compose-Setup**
  - Qdrant, Ollama und API als Container-Stack
  - Persistente Volumes für Datenbank und Modelle

---

## Noch nicht umgesetzt (mögliche nächste Schritte)

| Feature | Beschreibung |
|---|---|
| Webhooks / Callbacks | Asynchrones Matching mit Callback-URL für lang laufende Batches |
| Authentifizierung | API-Key oder OAuth2 zum Absichern der Endpunkte |
| Mehrsprachige OCR | Weitere Tesseract-Sprachpakete (Französisch, Spanisch, etc.) |
| Anthropic-Provider aktivieren | Cloud-KI via Claude + Voyage AI in Produktion schalten |
