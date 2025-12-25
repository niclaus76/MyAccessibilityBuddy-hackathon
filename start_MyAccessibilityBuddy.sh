#!/bin/bash

# Start FastAPI server for MyAccessibilityBuddy
# This script starts the API server on port 8000

echo "Starting MyAccessibilityBuddy FastAPI server..."
echo "================================================"
echo ""

# Check if in correct directory
if [ ! -d "backend" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Check for existing instances and stop them
echo "Checking for existing instances..."
EXISTING_PIDS_8080=$(lsof -ti:8080)
EXISTING_PIDS_8000=$(lsof -ti:8000)
EXISTING_PIDS_3001=$(lsof -ti:3001)

if [ ! -z "$EXISTING_PIDS_8080" ]; then
    echo "Found existing server process(es) on port 8080: $EXISTING_PIDS_8080"
    echo "Stopping existing instances on port 8080..."
    kill $EXISTING_PIDS_8080 2>/dev/null
    sleep 1
fi

if [ ! -z "$EXISTING_PIDS_8000" ]; then
    echo "Found existing server process(es) on port 8000: $EXISTING_PIDS_8000"
    echo "Stopping existing instances on port 8000..."
    kill $EXISTING_PIDS_8000 2>/dev/null
    sleep 1
fi

if [ ! -z "$EXISTING_PIDS_3001" ]; then
    echo "Found existing server process(es) on port 3001: $EXISTING_PIDS_3001"
    echo "Stopping existing instances on port 3001..."
    kill $EXISTING_PIDS_3001 2>/dev/null
    sleep 1
fi

# Force kill if still running
STILL_RUNNING_8080=$(lsof -ti:8080)
STILL_RUNNING_8000=$(lsof -ti:8000)
STILL_RUNNING_3001=$(lsof -ti:3001)

if [ ! -z "$STILL_RUNNING_8080" ]; then
    echo "Force stopping remaining processes on port 8080..."
    kill -9 $STILL_RUNNING_8080 2>/dev/null
    sleep 1
fi

if [ ! -z "$STILL_RUNNING_8000" ]; then
    echo "Force stopping remaining processes on port 8000..."
    kill -9 $STILL_RUNNING_8000 2>/dev/null
    sleep 1
fi

if [ ! -z "$STILL_RUNNING_3001" ]; then
    echo "Force stopping remaining processes on port 3001..."
    kill -9 $STILL_RUNNING_3001 2>/dev/null
    sleep 1
fi

echo "Existing instances stopped."
echo ""

# Activate virtual environment
if [ -d "backend/venv" ]; then
    echo "Activating virtual environment..."
    source backend/venv/bin/activate
else
    echo "Warning: Virtual environment not found at backend/venv"
    echo "Please create it with: python3 -m venv backend/venv"
    exit 1
fi

# Check if FastAPI is installed
python3 -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: FastAPI not installed in backend/venv"
    echo ""
    echo "To install dependencies, run:"
    echo "  source backend/venv/bin/activate"
    echo "  pip install -r backend/requirements.txt"
    echo ""
    exit 1
fi

echo "Starting MyAccessibilityBuddy..."
echo "API Server: http://localhost:8000"
echo "API Documentation: http://localhost:8000/api/docs"
echo "Note: ECB-LLM OAuth will use port 3001 automatically when needed"
echo "Opening frontend in browser..."
echo "Press Ctrl+C to stop all servers"
echo ""

# Start frontend HTTP server on port 8080 (to avoid CORS issues with file://)
python3 backend/serve_frontend.py &
PID_8080=$!
sleep 1

# Open frontend in default browser via HTTP
xdg-open "http://localhost:8080/home.html" 2>/dev/null &

# Start uvicorn server on port 8000 (main API)
cd backend
python3 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload &
PID_8000=$!

echo ""
echo "Servers started:"
echo "  - Frontend on port 8080 (PID: $PID_8080)"
echo "  - Main API on port 8000 (PID: $PID_8000)"
echo ""

# Wait for either process to exit
wait -n

# Kill all background jobs when script exits
trap "kill $PID_8080 $PID_8000 2>/dev/null" EXIT

# Wait for all processes
wait
