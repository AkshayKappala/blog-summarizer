"""Logging configuration for Blog Summarizer."""

import sys
from loguru import logger

from src.config import get_settings, DATA_DIR


def setup_logger() -> None:
    """Configure loguru logger."""
    settings = get_settings()

    logger.remove()

    # Console output
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File output
    logger.add(
        DATA_DIR / "app.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days",
    )

    logger.info(f"Logger initialized with level: {settings.log_level}")
