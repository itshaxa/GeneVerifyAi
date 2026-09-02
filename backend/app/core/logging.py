"""Structured logging setup.

Configured once at application startup so every module can rely on a
consistent, parseable log format (important for future Alibaba Cloud
log collection).
"""

import logging
import logging.config


def configure_logging(level: str = "INFO") -> None:
    """Apply the application-wide logging configuration."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": level.upper(),
                "handlers": ["console"],
            },
        }
    )
