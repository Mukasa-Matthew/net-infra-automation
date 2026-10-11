#!/usr/bin/env bash
# ==============================================================================
# Script: health_check.sh
# Description: Comprehensive System and Network Interface Telemetry Utility
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
BOLD='\033[1m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

section() {
    echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}"
}

section_header() {
    echo -e "${CYAN}----------------------------------------------------------------------${NC}"
}

# ------------------------------------------------------------------------------
# 1. Host and Kernel Overview
# ------------------------------------------------------------------------------
section "1. HOST & KERNEL INFORMATION"
section_header
echo -e "Hostname:       ${BOLD}$(hostname -f 2>/dev/null || hostname)${NC}"
echo -e "Kernel Version: $(uname -r)"
echo -e "Architecture:   $(uname -m)"
echo -e "Uptime:         $(uptime -p 2>/dev/null || uptime)"
echo -e "Load Average:   $(uptime | awk -F'load average:' '{print $2}' | xargs)"

# ------------------------------------------------------------------------------
# 2. Compute & Memory Utilization
# ------------------------------------------------------------------------------
section "2. SYSTEM RESOURCE UTILIZATION"
section_header
echo -e "${BOLD}Memory Usage:${NC}"
if command -v free &>/dev/null; then
    free -h
else
    echo "Command 'free' unavailable."
fi

echo -e "\n${BOLD}Primary Filesystems Disk Usage:${NC}"
df -h -x tmpfs -x devtmpfs -x squashfs 2>/dev/null || df -h

# ------------------------------------------------------------------------------
# 3. Network Interface Telemetry
# ------------------------------------------------------------------------------
section "3. NETWORK INTERFACES & LINK STATUS"
section_header

if command -v ip &>/dev/null; then
    echo -e "${BOLD}Interface IP & Operational States:${NC}"
    ip -br addr show

    echo -e "\n${BOLD}Interface Error & Dropped Packets Counters:${NC}"
    ip -s link | awk '
        /^[0-9]+: / {iface=$2} 
        /RX:/ {getline; rx_drop=$4; rx_err=$3}
        /TX:/ {getline; tx_drop=$4; tx_err=$3; print "  " iface " -> RX errors: " rx_err ", drops: " rx_drop " | TX errors: " tx_err ", drops: " tx_drop}
    '
elif command -v ifconfig &>/dev/null; then
    ifconfig -s
else
    echo "Neither 'ip' nor 'ifconfig' command found."
fi

# ------------------------------------------------------------------------------
# 4. Routing Table & Gateway Connectivity
# ------------------------------------------------------------------------------
section "4. ROUTING & GATEWAY CONNECTIVITY"
section_header

DEFAULT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n1 || echo "")

if [[ -n "${DEFAULT_GW}" ]]; then
    echo -e "Default Gateway: ${BOLD}${DEFAULT_GW}${NC}"
    echo -n "Pinging Default Gateway (${DEFAULT_GW})... "
    if ping -c 2 -W 2 "${DEFAULT_GW}" &>/dev/null; then
        echo -e "${GREEN}[SUCCESS] Gateway reachable.${NC}"
    else
        echo -e "${YELLOW}[WARNING] Gateway unreachable or ICMP blocked.${NC}"
    fi
else
    echo -e "${YELLOW}[WARN] No default gateway detected.${NC}"
fi

# ------------------------------------------------------------------------------
# 5. DNS Resolution & Latency
# ------------------------------------------------------------------------------
section "5. DNS RESOLUTION PROBE"
section_header

TEST_DOMAINS=("cloudflare.com" "google.com")
for domain in "${TEST_DOMAINS[@]}"; do
    echo -n "Resolving '${domain}'... "
    START_TIME=$(date +%s%N)
    if getent hosts "${domain}" &>/dev/null; then
        END_TIME=$(date +%s%N)
        LATENCY=$(( (END_TIME - START_TIME) / 1000000 ))
        echo -e "${GREEN}[OK]${NC} Latency: ${LATENCY}ms"
    else
        echo -e "${RED}[FAILED] Resolution error.${NC}"
    fi
done

# ------------------------------------------------------------------------------
# 6. Active Listening Sockets
# ------------------------------------------------------------------------------
section "6. ACTIVE LISTENING PORTS"
section_header

if command -v ss &>/dev/null; then
    ss -tuln | head -n 15
elif command -v netstat &>/dev/null; then
    netstat -tuln | head -n 15
else
    echo "'ss' or 'netstat' not found."
fi

echo -e "\n${BOLD}${GREEN}======================================================================${NC}"
echo -e "${BOLD}${GREEN} Telemetry inspection completed at $(date -u +"%Y-%m-%dT%H:%M:%SZ") ${NC}"
echo -e "${BOLD}${GREEN}======================================================================${NC}\n"
