#!/bin/bash

# LiveBench Dashboard Startup Script
# This script starts both the backend API and frontend dashboard

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
elif command -v conda &>/dev/null; then
    eval "$(conda shell.bash hook)"
    conda activate base 2>/dev/null || true
fi

echo "🚀 Starting LiveBench Dashboard..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${BLUE}📦 Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
fi

# Build frontend
echo -e "${BLUE}🔨 Building frontend...${NC}"
cd frontend
npm run build
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend build failed${NC}"
    exit 1
fi
cd ..
echo -e "${GREEN}✓ Frontend built${NC}"
echo ""

# Function to kill existing processes on a port
kill_port() {
    local port=$1
    local name=$2
    local pid=$(lsof -ti:$port 2>/dev/null)

    if [ -n "$pid" ]; then
        echo -e "${YELLOW}⚠️  Found existing $name (PID: $pid) on port $port${NC}"
        echo -e "${YELLOW}   Killing...${NC}"
        kill -9 $pid 2>/dev/null
        sleep 1
        # Verify it's killed
        if lsof -ti:$port &>/dev/null; then
            echo -e "${RED}❌ Failed to kill $name${NC}"
            return 1
        else
            echo -e "${GREEN}✓ Killed existing $name${NC}"
        fi
    else
        echo -e "${GREEN}✓ No existing $name on port $port${NC}"
    fi
    return 0
}

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${BLUE}🛑 Stopping services...${NC}"
    kill $API_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Kill existing processes before starting
echo -e "${BLUE}🔍 Checking for existing services...${NC}"
kill_port 8000 "Backend API"
kill_port 3010 "Frontend"
kill_port 3001 "Frontend (legacy)"
kill_port 3002 "Frontend (legacy)"
kill_port 3003 "Frontend (legacy)"
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Backend API (module-safe) via uvicorn
echo -e "${BLUE}🔧 Starting Backend API...${NC}"
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
uvicorn livebench.api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!

# Wait for API to start
sleep 3

# Check if API is running
if ! kill -0 $API_PID 2>/dev/null; then
    echo -e "${RED}❌ Failed to start Backend API${NC}"
    echo "Check logs/api.log for details"
    exit 1
fi

echo -e "${GREEN}✓ Backend API started (PID: $API_PID)${NC}"

# Ensure frontend port is free right before starting
kill_port 3010 "Frontend"
if command -v fuser &>/dev/null; then
  fuser -k 3010/tcp 2>/dev/null || true
  sleep 1
fi

# Start legacy Vite dashboard (optional)
echo -e "${BLUE}🎨 Starting Legacy Frontend Dashboard (Vite)...${NC}"
cd frontend
npm run dev -- --host 0.0.0.0 --port 3010 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 3

# Check if frontend is running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Failed to start Frontend${NC}"
    echo "Check logs/frontend.log for details"
    kill $API_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 LiveBench Dashboard is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BLUE}📊 Dashboard:${NC}  http://localhost:3010"
echo -e "  ${BLUE}🔧 Backend API:${NC} http://localhost:8000"
echo -e "  ${BLUE}📚 API Docs:${NC}    http://localhost:8000/docs"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo -e "  API:      tail -f logs/api.log"
echo -e "  Frontend: tail -f logs/frontend.log"
echo ""
echo -e "${RED}Press Ctrl+C to stop all services${NC}"
echo ""

# Keep script running
wait
