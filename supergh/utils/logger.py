"""Logging system for supergh — configurable log level, file output."""

from __future__ import annotations

import logging
from pathlib import Path

from supergh.config import get_config

LOG_DIR = Path.home() / ".supergh" / "logs"
LOG_FILE = LOG_DIR / "sgh.log"

_logger: logging.Logger | None = None

LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "off": logging.CRITICAL + 1,
}


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    _logger = logging.getLogger("supergh")
    _logger.handlers.clear()

    # Read log level from config
    cfg = get_config()
    level_str = cfg.get("core.log_level", "info")
    level = LEVELS.get(level_str, logging.INFO)

    if level > logging.CRITICAL:
        _logger.setLevel(logging.CRITICAL + 1)
        _logger.addHandler(logging.NullHandler())
        return _logger

    _logger.setLevel(level)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    _logger.addHandler(fh)

    return _logger


def set_log_level(level_str: str) -> bool:
    """Update log level in config and apply immediately."""
    level_str = level_str.lower()
    if level_str not in LEVELS:
        return False
    cfg = get_config()
    cfg.set("core.log_level", level_str)
    # Reset logger so it picks up new level
    global _logger
    _logger = None
    return True


def get_current_level() -> str:
    cfg = get_config()
    return cfg.get("core.log_level", "info")
