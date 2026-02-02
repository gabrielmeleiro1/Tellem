#!/bin/bash
# Audiobook Creator - Launch Script
# ================================
# Starts both the Python gRPC backend and SwiftUI frontend

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/Users/main/Developer/Audiobook"
BACKEND_PORT=50051
BACKEND_PID=""

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        echo -e "${BLUE}Stopping backend server (PID: $BACKEND_PID)...${NC}"
        kill $BACKEND_PID 2>/dev/null || true
        wait $BACKEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Done!${NC}"
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Audiobook Creator - Full Stack Launcher  ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Check if running from correct directory
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}Error: Project directory not found at $PROJECT_DIR${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

# Check virtual environment
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found. Please run:${NC}"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

# Check if port is already in use
echo -e "${BLUE}Checking port $BACKEND_PORT...${NC}"
if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Port $BACKEND_PORT is already in use.${NC}"
    echo -e "${YELLOW}Attempting to kill existing process...${NC}"
    kill -9 $(lsof -t -i :$BACKEND_PORT) 2>/dev/null || true
    sleep 1
fi

# Start backend server
echo -e "${BLUE}Starting gRPC backend server on port $BACKEND_PORT...${NC}"
cd "$PROJECT_DIR/swift-ui/BackendGRPC"

# Set PYTHONPATH for imports
export PYTHONPATH="${PYTHONPATH}:$PROJECT_DIR:$PROJECT_DIR/swift-ui/BackendGRPC"

# Run server in background
python server.py &
BACKEND_PID=$!

# Wait for server to be ready
echo -e "${BLUE}Waiting for backend to start...${NC}"
RETRIES=30
while [ $RETRIES -gt 0 ]; do
    if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend server is ready!${NC}"
        break
    fi
    sleep 0.5
    RETRIES=$((RETRIES - 1))
    echo -n "."
done

if [ $RETRIES -eq 0 ]; then
    echo -e "\n${RED}Error: Backend server failed to start within 15 seconds${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Starting SwiftUI Frontend...             ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Run SwiftUI app
cd "$PROJECT_DIR/swift-ui"
echo -e "${BLUE}Building and running SwiftUI app...${NC}"
echo -e "${YELLOW}(Press Ctrl+C to stop both frontend and backend)${NC}"
echo ""

# Run the app (blocking call)
swift run

# Script ends here (cleanup trap will run)
