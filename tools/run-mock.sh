#!/bin/bash
# FranklinWH Battery Manager - Mock Mode Launcher
# Usage: ./run-mock.sh [-q|--quiet]

cd "$(dirname "$0")"

# Parse arguments
QUIET=false
if [[ "$1" == "-q" ]] || [[ "$1" == "--quiet" ]]; then
    QUIET=true
    shift
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found!"
    echo "Run: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi

# Set mock mode environment variable
export MOCK_MODE=true
export LOG_LEVEL=INFO

# Create logs directory if it doesn't exist
mkdir -p data/logs

# Run the application
if [ "$QUIET" = true ]; then
    # Quiet mode: log to file only
    python -m src.main >> data/logs/franklinwh-mock.log 2>&1
else
    # Verbose mode: log to both terminal and file
    echo "🎭 Starting FranklinWH Battery Manager in MOCK MODE..."
    echo "   Web UI: http://localhost:8080"
    echo "   Logs: data/logs/franklinwh-mock.log"
    echo ""
    python -m src.main 2>&1 | tee -a data/logs/franklinwh-mock.log
fi
