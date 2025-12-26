#!/bin/bash
set -e

# MyAccessibilityBuddy Docker Entrypoint Script
# This script starts both the frontend server and FastAPI backend

echo "=========================================="
echo "MyAccessibilityBuddy Starting..."
echo "=========================================="
echo ""

# Check if .env file exists
if [ ! -f "/app/backend/.env" ]; then
    echo "WARNING: No .env file found at /app/backend/.env"
    echo "Please create one with your API credentials:"
    echo "  - For OpenAI: OPENAI_API_KEY=sk-..."
    echo "  - For ECB-LLM: CLIENT_ID_U2A=... and CLIENT_SECRET_U2A=..."
    echo ""
fi

# Check configuration
if [ -f "/app/backend/config/config.json" ]; then
    echo "✓ Configuration file found"
    LLM_PROVIDER=$(python3 -c "import json; print(json.load(open('/app/backend/config/config.json')).get('llm_provider', 'Unknown'))")
    MODEL=$(python3 -c "import json; print(json.load(open('/app/backend/config/config.json')).get('model', 'Unknown'))")
    echo "  LLM Provider: $LLM_PROVIDER"
    echo "  Model: $MODEL"
else
    echo "✗ Configuration file not found!"
    exit 1
fi

echo ""
echo "Starting services..."
echo "  - Frontend server on port 8080"
echo "  - FastAPI backend on port 8000"
if [ "$LLM_PROVIDER" = "ECB-LLM" ]; then
    echo "  - OAuth callback on port 3001 (managed by ecb_llm_client)"
fi
echo ""

# Create required directories if they don't exist
mkdir -p /app/input/images /app/input/context
mkdir -p /app/output/alt-text /app/output/reports
mkdir -p /app/logs

# Start frontend server in background
python3 /app/backend/serve_frontend.py &
FRONTEND_PID=$!
echo "✓ Frontend server started (PID: $FRONTEND_PID)"

# Give frontend server time to start
sleep 2

# Start FastAPI backend
cd /app/backend
echo "✓ Starting FastAPI backend..."
echo ""
echo "=========================================="
echo "Access the application at:"
echo "  Frontend: http://localhost:8080/home.html"
echo "  API Docs: http://localhost:8000/api/docs"
echo "=========================================="
echo ""

# Execute the main command (FastAPI server)
exec python3 -m uvicorn api:app --host 0.0.0.0 --port 8000
