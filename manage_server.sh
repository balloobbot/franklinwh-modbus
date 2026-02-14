#!/bin/bash

# FranklinWH Battery Manager - Server Management Script
# Usage: ./manage_server.sh [status|stop|kill|restart|start]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/.server.pid"

# Function to find running server processes
find_servers() {
    # Look for Python processes running src.main or src.web_server
    ps aux | grep -E "python.*src\.(main|web_server)" | grep -v grep || true
}

# Function to count running servers
count_servers() {
    find_servers | wc -l
}

# Function to display status
show_status() {
    echo -e "${BLUE}=== FranklinWH Battery Manager - Server Status ===${NC}"
    echo
    
    local count=$(count_servers)
    
    if [ "$count" -eq 0 ]; then
        echo -e "${YELLOW}⚠ No server processes running${NC}"
        echo
        echo "To start the server:"
        echo "  ./run.sh         # Using run script"
        echo "  ./venv/bin/python3 -m src.main  # Direct start"
    else
        echo -e "${GREEN}✓ Found $count server process(es) running:${NC}"
        echo
        printf "%-8s %-8s %-6s %-6s %-20s %s\n" "PID" "CPU%" "MEM%" "TIME" "STARTED" "COMMAND"
        printf "%-8s %-8s %-6s %-6s %-20s %s\n" "---" "----" "----" "----" "-------" "-------"
        
        find_servers | while read -r line; do
            pid=$(echo "$line" | awk '{print $2}')
            cpu=$(echo "$line" | awk '{print $3}')
            mem=$(echo "$line" | awk '{print $4}')
            time=$(echo "$line" | awk '{print $10}')
            started=$(ps -o lstart= -p "$pid" 2>/dev/null | awk '{print $2 " " $3 " " $4}' || echo "unknown")
            cmd=$(echo "$line" | awk '{print $11 " " $12}')
            printf "%-8s %-8s %-6s %-6s %-20s %s\n" "$pid" "$cpu" "$mem" "$time" "$started" "$cmd"
        done
        
        echo
        echo -e "${BLUE}Ports in use:${NC}"
        ss -tlnp 2>/dev/null | grep -E "(8080|8000)" || netstat -tlnp 2>/dev/null | grep -E "(8080|8000)" || echo "  (cannot determine - ss/netstat not available)"
    fi
    echo
}

# Function to stop servers gracefully
stop_servers() {
    local timeout=${1:-10}
    local count=$(count_servers)
    
    if [ "$count" -eq 0 ]; then
        echo -e "${YELLOW}⚠ No server processes to stop${NC}"
        return 0
    fi
    
    echo -e "${BLUE}Stopping $count server process(es) gracefully...${NC}"
    echo "(Timeout: ${timeout}s before force kill)"
    echo
    
    # Send SIGTERM (graceful shutdown)
    find_servers | awk '{print $2}' | while read -r pid; do
        echo -e "  Sending SIGTERM to PID $pid..."
        kill -TERM "$pid" 2>/dev/null || true
    done
    
    # Wait for processes to stop
    local waited=0
    while [ "$(count_servers)" -gt 0 ] && [ "$waited" -lt "$timeout" ]; do
        sleep 1
        ((waited++))
        echo -n "."
    done
    echo
    
    local remaining=$(count_servers)
    if [ "$remaining" -eq 0 ]; then
        echo -e "${GREEN}✓ All servers stopped gracefully${NC}"
        rm -f "$PID_FILE"
        return 0
    else
        echo -e "${YELLOW}⚠ $remaining process(es) still running after ${timeout}s${NC}"
        return 1
    fi
}

# Function to kill servers forcefully
kill_servers() {
    local count=$(count_servers)
    
    if [ "$count" -eq 0 ]; then
        echo -e "${YELLOW}⚠ No server processes to kill${NC}"
        return 0
    fi
    
    echo -e "${RED}Force killing $count server process(es)...${NC}"
    echo
    
    find_servers | awk '{print $2}' | while read -r pid; do
        echo -e "  Sending SIGKILL to PID $pid..."
        kill -KILL "$pid" 2>/dev/null || true
    done
    
    sleep 1
    
    local remaining=$(count_servers)
    if [ "$remaining" -eq 0 ]; then
        echo -e "${GREEN}✓ All servers killed${NC}"
        rm -f "$PID_FILE"
    else
        echo -e "${RED}✗ Failed to kill $remaining process(es) - may need sudo${NC}"
        return 1
    fi
}

# Function to start server
start_server() {
    echo -e "${BLUE}Starting FranklinWH Battery Manager...${NC}"
    echo
    
    # Create logs directory
    mkdir -p "${SCRIPT_DIR}/data/logs"
    
    if [ -f "${SCRIPT_DIR}/run.sh" ]; then
        echo "Using run.sh script..."
        cd "$SCRIPT_DIR" && ./run.sh > data/logs/franklinwh.log 2>&1 &
    elif [ -d "${SCRIPT_DIR}/venv" ]; then
        echo "Starting with venv Python..."
        cd "$SCRIPT_DIR" && ./venv/bin/python3 -m src.main > data/logs/franklinwh.log 2>&1 &
    else
        echo -e "${RED}✗ Cannot find run.sh or venv${NC}"
        return 1
    fi
    
    echo
    echo -e "${GREEN}✓ Server starting in background${NC}"
    echo "  Log file: data/logs/franklinwh.log"
    echo "  Wait a few seconds, then check status with: $0 status"
    echo "  Watch logs with: tail -f data/logs/franklinwh.log"
}

# Function to restart server
restart_server() {
    stop_servers 5 || kill_servers
    sleep 2
    start_server
}

# Function to show help
show_help() {
    echo "FranklinWH Battery Manager - Server Management Script"
    echo
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  status    Show running server processes (default)"
    echo "  stop      Gracefully stop all servers (SIGTERM, 10s timeout)"
    echo "  kill      Force kill all servers (SIGKILL)"
    echo "  restart   Stop then start the server"
    echo "  start     Start the server"
    echo "  help      Show this help message"
    echo
    echo "Examples:"
    echo "  $0              # Check status"
    echo "  $0 stop         # Graceful shutdown"
    echo "  $0 kill         # Force kill if stop doesn't work"
    echo "  $0 restart      # Full restart"
}

# Main logic
case "${1:-status}" in
    status|s|""|list|ls)
        show_status
        ;;
    stop|down|quit|q)
        stop_servers 10
        ;;
    kill|force|f)
        kill_servers
        ;;
    start|up|run)
        start_server
        ;;
    restart|reboot|r)
        restart_server
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}✗ Unknown command: $1${NC}"
        echo
        show_help
        exit 1
        ;;
esac
