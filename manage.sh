#!/bin/bash

# =============================================================================
# AutoCoder Management Script
# =============================================================================
# This script automates pulling the latest code, stopping existing processes,
# and launching the application in either Development or Production mode.
#
# Usage:
#   ./manage.sh [mode]
#
# Modes:
#   dev   - Stop existing, pull latest, and start with hot-reload (Default)
#   prod  - Stop existing, pull latest, build frontend, and start production
#   stop  - Just stop all running app processes
#   pull  - Just pull the latest changes from master
# =============================================================================

MODE=${1:-"dev"}

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

stop_processes() {
    echo -e "${YELLOW}Stopping all running AutoCoder processes...${NC}"
    # Kill Vite, Uvicorn, and Python launcher processes
    # Using pkill -f for cleaner matching
    pkill -9 -f "vite" 2>/dev/null
    pkill -9 -f "uvicorn" 2>/dev/null
    pkill -9 -f "start_ui.py" 2>/dev/null
    pkill -9 -f "start_ui.sh" 2>/dev/null
    echo -e "${GREEN}All processes stopped.${NC}"
}

pull_latest() {
    echo -e "${BLUE}Pulling latest changes from origin/master...${NC}"
    git fetch origin master
    git merge origin/master
    echo -e "${GREEN}Repository updated.${NC}"
}

case $MODE in
    "stop")
        stop_processes
        exit 0
        ;;
    "pull")
        pull_latest
        exit 0
        ;;
    "dev")
        stop_processes
        pull_latest
        echo -e "${BLUE}Launching in DEVELOPMENT mode (Hotload enabled)...${NC}"
        python3 start_ui.py --dev
        ;;
    "prod")
        stop_processes
        pull_latest
        echo -e "${BLUE}Launching in PRODUCTION mode...${NC}"
        python3 start_ui.py
        ;;
    *)
        echo -e "${RED}Invalid mode: $MODE${NC}"
        echo "Valid modes: dev, prod, stop, pull"
        exit 1
        ;;
esac
