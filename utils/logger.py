"""
utils/logger.py
Structured logging utility for systems and network automation scripts.
Provides ANSI colored console output and optional structured JSON formatting.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any


class ColoredConsoleFormatter(logging.Formatter):
    """Console formatter adding ANSI color codes for enhanced terminal readability."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    GRAY = "\033[90m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"

    LEVEL_COLORS = {
        logging.DEBUG: GRAY,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: f"{RED}{BOLD}",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        time_str = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level_label = f"{color}[{record.levelname:<7}]{self.RESET}"
        name_label = f"{self.GRAY}({record.name}){self.RESET}"
        message = record.getMessage()

        # Handle extra contextual metadata if provided
        extra = getattr(record, "extra_data", None)
        extra_str = f" {self.MAGENTA}{json.dumps(extra)}{self.RESET}" if extra else ""

        return f"{self.GRAY}{time_str}{self.RESET} {level_label} {name_label} {message}{extra_str}"


class JsonFormatter(logging.Formatter):
    """JSON log formatter for centralized log aggregators (ELK, Datadog, CloudWatch)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        extra = getattr(record, "extra_data", None)
        if extra and isinstance(extra, dict):
            log_entry["context"] = extra

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_logger(
    name: str = "net-infra",
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    json_output: bool = False,
) -> logging.Logger:
    """
    Factory function to configure and retrieve a structured logger.

    Args:
        name: Name of the logger / component.
        level: Minimum log level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        log_file: Optional file path to persist logs.
        json_output: If True, formats output as single-line JSON.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Determine log level from arg or environment variable
    env_level = os.getenv("LOG_LEVEL", "INFO").upper()
    target_level = getattr(logging, (level or env_level).upper(), logging.INFO)
    logger.setLevel(target_level)

    # Prevent duplicate handlers if get_logger is called repeatedly
    if logger.handlers:
        return logger

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(target_level)

    if json_output or os.getenv("LOG_FORMAT", "").lower() == "json":
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(ColoredConsoleFormatter())

    logger.addHandler(console_handler)

    # Optional File Handler
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(target_level)
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

    return logger
