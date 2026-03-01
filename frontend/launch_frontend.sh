#!/bin/bash

echo "🎉 Launching TeacherPilot Frontend..."
echo ""

# Clear any previous cache
rm -rf node_modules/.vite 2>/dev/null

echo "✅ Cache cleared"
echo "Starting Vite development server on port 3000..."
echo ""

# Start the server
npm run dev

echo ""
echo "🚀 Frontend should now be running at http://localhost:3000"