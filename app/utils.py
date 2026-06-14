"""Loguru logging setup: colored stdout plus rotating file sinks."""

from __future__ import annotations

import os
import sys
from zoneinfo import ZoneInfo

from loguru import logger


def timezone_filter(record):
    """Attach UTC+8 (Asia/Shanghai) timezone info to log records"""
    record["time"] = record["time"].astimezone(ZoneInfo("Asia/Shanghai"))
    return record


def init_log(**sink_channel):
    # Make stdout tolerant of unicode (emojis, ×, non-ASCII) on legacy Windows
    # consoles, where the default cp1251/cp1252 codec would crash the log handler.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()

    persistent_format = (
        "<g>{time:YYYY-MM-DD HH:mm:ss}</g> | "
        "<lvl>{level}</lvl>    | "
        "<c><u>{name}</u></c>:{function}:{line} | "
        "{message} - "
        "{extra}"
    )
    stdout_format = (
        "<g>{time:YYYY-MM-DD HH:mm:ss}</g> | "
        "<lvl>{level:<8}</lvl>    | "
        "<c>{name}</c>:<c>{function}</c>:<c>{line}</c> | "
        "<n>{message}</n>"
    )

    logger.remove()
    logger.add(
        sink=sys.stdout,
        colorize=True,
        level=log_level,
        format=stdout_format,
        diagnose=False,
        filter=timezone_filter,
    )
    if sink_channel.get("error"):
        logger.add(
            sink=sink_channel.get("error"),
            level="ERROR",
            rotation="5 MB",
            retention="7 days",
            encoding="utf8",
            diagnose=False,
            filter=timezone_filter,
        )
    if sink_channel.get("runtime"):
        logger.add(
            sink=sink_channel.get("runtime"),
            level="TRACE",
            rotation="5 MB",
            retention="7 days",
            encoding="utf8",
            diagnose=False,
            filter=timezone_filter,
        )
    if sink_channel.get("serialize"):
        logger.add(
            sink=sink_channel.get("serialize"),
            level="DEBUG",
            format=persistent_format,
            encoding="utf8",
            diagnose=False,
            serialize=True,
            filter=timezone_filter,
        )
    return logger
