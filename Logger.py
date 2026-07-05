"""
Centralised logging setup. Every module should call get_logger(__name__)
rather than configuring its own handlers - keeps format and rotation
consistent once this is running unattended on a VPS.

Two rotating files are kept: bot.log (everything >= configured level) and
errors.log (ERROR and above only), so an operator can tail one file to see
only what actually needs attention.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        LOG_DIR / "bot.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    error_handler = RotatingFileHandler(
        LOG_DIR / "errors.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    _configured = True


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    _configure_root(level)
    return logging.getLogger(name)
