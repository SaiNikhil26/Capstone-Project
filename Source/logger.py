import logging
import os
from datetime import datetime


def get_logger(name: str) -> logging.Logger:
    """
    Creates a logger for the given module name.
    - Writes to logs/<name>.log
    - Also prints to console
    - Each log file is named after the module (e.g. ingest.log, retriever.log)
    """

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Format ──────────────────────────────────────────
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ── File handler — logs/<name>.log ──────────────────
    file_handler = logging.FileHandler(
        filename=f"logs/{name}.log",
        mode="a",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # ── Console handler ──────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger