#!/bin/bash
# FranklinWH Development Environment Setup
# Run this whenever you start working: source setup_dev.sh

set -e

echo "🔧 FranklinWH Dev Environment Setup"
echo "===================================="

# 1. Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# 2. Activate venv
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# 3. Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip --quiet

# 4. Install all requirements
echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt --quiet

# 5. Verify critical imports
echo "🔍 Verifying critical dependencies..."
python3 -c "import fastapi, pysunspec2, httpx, jsonschema" 2>/dev/null && echo "✅ All imports OK" || echo "❌ Import check failed"

# 6. Show Python version
echo "🐍 Python: $(python --version)"

# 7. Show environment info
echo "📍 Virtual env: $VIRTUAL_ENV"

echo ""
echo "✅ Development environment ready!"
echo "💡 Run: python src/main.py"
