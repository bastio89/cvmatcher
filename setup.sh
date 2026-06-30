#!/usr/bin/env bash
set -e

echo "=== CV Mapper Setup ==="

# 1. Qdrant & Ollama via Docker starten
echo "[1/4] Starte Qdrant + Ollama via Docker Compose..."
docker compose up -d qdrant ollama

# 2. Kurz warten bis Ollama bereit ist
echo "[2/4] Warte auf Ollama..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done

# 3. Modelle pullen
echo "[3/4] Lade KI-Modelle (einmalig, kann einige Minuten dauern)..."
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.2

# 4. Python-Abhängigkeiten installieren
echo "[4/4] Installiere Python-Pakete..."
pip install -r requirements.txt

echo ""
echo "=== Setup abgeschlossen ==="
echo "API starten: uvicorn app.main:app --reload"
echo "Docs:        http://localhost:8000/docs"
