#!/bin/bash
set -e

echo "============================================"
echo "  TRACELIGHT AI SIDECARS — DEMO LAUNCHER"
echo "============================================"
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "ERROR: Docker Compose is not installed."
    exit 1
fi

# Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example and add your API keys."
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your OPENAI_API_KEY and GOOGLE_CLOUD_PROJECT"
    exit 1
fi

# Generate templates if not present
if [ ! -f safe-harbor/templates/lbo_template.xlsx ]; then
    echo "[SETUP] Generating Excel templates..."
    cd safe-harbor/scripts && python3 generate_templates.py && cd ../..
    echo "[SETUP] Templates generated."
fi

if [ ! -f shield-wall/tests/fixtures/sample_questionnaire.xlsx ]; then
    echo "[SETUP] Generating sample questionnaire..."
    cd shield-wall/scripts && python3 generate_fixtures.py && cd ../..
    echo "[SETUP] Questionnaire generated."
fi

echo ""
echo "[BUILD] Building Docker images (this may take a few minutes on first run)..."
docker compose build

echo ""
echo "[START] Starting all services..."
docker compose up -d

echo ""
echo "============================================"
echo "  DEMO READY"
echo "============================================"
echo ""
echo "  Launcher:        http://localhost:5173"
echo "  Safe-Harbor:     http://localhost:5174"
echo "  Shield-Wall:     http://localhost:5175"
echo ""
echo "  Safe-Harbor API: http://localhost:8000/docs"
echo "  Shield-Wall API: http://localhost:8001/docs"
echo ""
echo "  To stop: docker compose down"
echo "============================================"

# Open launcher in default browser
if command -v open &> /dev/null; then
    open http://localhost:5173
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173
fi
