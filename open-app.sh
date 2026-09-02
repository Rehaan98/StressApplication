#!/usr/bin/env bash
# Quick launcher - opens the application in your default browser

echo "🚀 Opening Psychological Stress AI..."
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "   Login with:"
echo "   📧 user@stressai.com / User@2026"
echo ""

# Check if servers are running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Backend is not running on port 8000"
    echo "   Start it with: ./start.sh backend"
    exit 1
fi

if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "❌ Frontend is not running on port 3000"
    echo "   Start it with: ./start.sh frontend"
    exit 1
fi

echo "✅ Both servers are running!"
echo ""
echo "Opening browser..."

# Open in default browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:3000
else
    echo "Please open http://localhost:3000 in your browser"
fi
