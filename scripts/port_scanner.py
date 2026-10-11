#!/usr/bin/env python3
"""
scripts/port_scanner.py
High-performance, multi-threaded network port and service discovery utility.
Features service identification, banner grabbing, and tabular or JSON output.
"""

import sys
import os
import socket
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

# Ensure repository root is on sys.path for utils imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import get_logger

logger = get_logger("port-scanner")

COMMON_PORTS: Dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB / Microsoft-DS",
    1433: "Microsoft SQL Server",
    1521: "Oracle DB",
    3306: "MySQL / MariaDB",
    3389: "RDP (Remote Desktop)",
    5432: "PostgreSQL",
    6379: "Redis",
    8000: "HTTP-Alt",
    8080: "HTTP-Proxy / Dev",
    8443: "HTTPS-Alt",
    9000: "Traefik Dashboard / SonarQube",
    9090: "Prometheus",
    9200: "Elasticsearch",
    27017: "MongoDB",
}


def grab_banner(host: str, port: int, timeout: float = 1.0) -> Optional[str]:
    """Attempts to grab an initial application banner from an open port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))

            # Trigger response for HTTP/HTTPS ports
            if port in (80, 8080, 8000):
                s.sendall(b"HEAD / HTTP/1.0\r\n\r\n")

            banner = s.recv(1024).decode("utf-8", errors="ignore").strip()
            # Return first line of banner
            return banner.split("\n")[0] if banner else None
    except Exception:
        return None


def scan_port(host: str, port: int, timeout: float = 1.0, banner_grab: bool = False) -> Optional[Dict[str, Any]]:
    """Probes a single TCP port on target host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            if result == 0:
                service = COMMON_PORTS.get(port, "Unknown Service")
                banner = grab_banner(host, port, timeout) if banner_grab else None
                return {
                    "port": port,
                    "state": "OPEN",
                    "service": service,
                    "banner": banner or "-",
                }
    except Exception as e:
        logger.debug(f"Error scanning port {port}: {e}")
    return None


def parse_ports(port_arg: str) -> List[int]:
    """Parses port specifications: 'common', '80,443,8080', or '1-1024'."""
    if port_arg.lower() == "common":
        return sorted(COMMON_PORTS.keys())

    ports = set()
    for part in port_arg.split(","):
        part = part.strip()
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start, end = int(start_str), int(end_str)
            if start > end or start < 1 or end > 65535:
                raise ValueError(f"Invalid port range: {part}")
            ports.update(range(start, end + 1))
        else:
            p = int(part)
            if p < 1 or p > 65535:
                raise ValueError(f"Port out of range: {p}")
            ports.add(p)
    return sorted(ports)


def print_results_table(target: str, ip: str, results: List[Dict[str, Any]]) -> None:
    """Formats scan results into a readable CLI table."""
    print("\n" + "=" * 70)
    print(f" PORT SCAN REPORT: {target} ({ip})")
    print("=" * 70)
    print(f"{'PORT':<10} {'STATE':<10} {'SERVICE':<25} {'BANNER'}")
    print("-" * 70)

    if not results:
        print("No open ports discovered.")
    else:
        for r in results:
            print(f"{r['port']:<10} {r['state']:<10} {r['service']:<25} {r['banner']}")
    print("=" * 70 + "\n")


def run_scanner():
    parser = argparse.ArgumentParser(
        description="High-performance network port and service scanning utility."
    )
    parser.add_argument(
        "-t", "--target", required=True, help="Target hostname or IP address to scan"
    )
    parser.add_argument(
        "-p",
        "--ports",
        default="common",
        help="Port specification (e.g. 'common', '22,80,443', '1-1000'). Default: 'common'",
    )
    parser.add_argument(
        "-w", "--timeout", type=float, default=1.0, help="Connection timeout in seconds (default: 1.0)"
    )
    parser.add_argument(
        "-c", "--concurrency", type=int, default=50, help="Maximum concurrent worker threads (default: 50)"
    )
    parser.add_argument(
        "-b", "--banner", action="store_true", help="Attempt application service banner grabbing"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )

    args = parser.parse_args()

    # Resolve target host
    try:
        resolved_ip = socket.gethostbyname(args.target)
        logger.info(f"Resolved target '{args.target}' to {resolved_ip}")
    except socket.gaierror as e:
        logger.error(f"Failed to resolve host '{args.target}': {e}")
        sys.exit(1)

    # Parse port range
    try:
        target_ports = parse_ports(args.ports)
    except ValueError as e:
        logger.error(f"Port parsing error: {e}")
        sys.exit(1)

    logger.info(
        f"Scanning {len(target_ports)} port(s) on {resolved_ip} with concurrency={args.concurrency}..."
    )

    open_ports: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_port = {
            executor.submit(scan_port, resolved_ip, port, args.timeout, args.banner): port
            for port in target_ports
        }

        for future in as_completed(future_to_port):
            result = future.result()
            if result:
                open_ports.append(result)
                logger.info(
                    f"Found open port: {result['port']}/TCP ({result['service']})"
                )

    # Sort results numerically
    open_ports.sort(key=lambda x: x["port"])

    if args.json:
        output_payload = {
            "target": args.target,
            "ip": resolved_ip,
            "scanned_ports_count": len(target_ports),
            "open_ports_count": len(open_ports),
            "open_ports": open_ports,
        }
        print(json.dumps(output_payload, indent=2))
    else:
        print_results_table(args.target, resolved_ip, open_ports)


if __name__ == "__main__":
    run_scanner()
