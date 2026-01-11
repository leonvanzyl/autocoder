#!/bin/bash
#
# Autocoder Deployment Script (Unix)
# ===================================
#
# Usage:
#   ./deploy.sh start     - Start all services
#   ./deploy.sh stop      - Stop all services
#   ./deploy.sh restart   - Restart all services
#   ./deploy.sh status    - Show service status
#   ./deploy.sh logs      - Tail logs
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════╗"
    echo "║       Autocoder Deploy Manager       ║"
    echo "╚══════════════════════════════════════╝"
    echo -e "${NC}"
}

# Ensure Python is available
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON=python3
    elif command -v python &> /dev/null; then
        PYTHON=python
    else
        echo -e "${RED}Error: Python not found${NC}"
        exit 1
    fi
}

# Main
print_header
check_python

case "${1:-help}" in
    start)
        echo -e "${GREEN}Starting services...${NC}"
        $PYTHON deploy.py start "${@:2}"
        ;;
    stop)
        echo -e "${YELLOW}Stopping services...${NC}"
        $PYTHON deploy.py stop "${@:2}"
        ;;
    restart)
        echo -e "${YELLOW}Restarting services...${NC}"
        $PYTHON deploy.py restart "${@:2}"
        ;;
    status)
        $PYTHON deploy.py status
        ;;
    logs)
        $PYTHON deploy.py logs "${@:2}"
        ;;
    help|--help|-h)
        echo "Usage: $0 {start|stop|restart|status|logs} [options]"
        echo ""
        echo "Commands:"
        echo "  start [backend|frontend]    Start services (default: all)"
        echo "  stop [backend|frontend]     Stop services (default: all)"
        echo "  restart [backend|frontend]  Restart services (default: all)"
        echo "  status                      Show service status"
        echo "  logs [backend|frontend]     Tail service logs"
        echo ""
        echo "Options:"
        echo "  -b, --backend-port PORT     Set backend port"
        echo "  -f, --frontend-port PORT    Set frontend port"
        echo ""
        echo "Examples:"
        echo "  $0 start                    Start all services"
        echo "  $0 start backend            Start only backend"
        echo "  $0 start -b 8080            Start with custom backend port"
        echo "  $0 status                   Check service status"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Run '$0 help' for usage"
        exit 1
        ;;
esac
