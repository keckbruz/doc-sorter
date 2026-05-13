from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional


def setup_logging(log_file: Optional[Path] = None, verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("doc_cleaner")
    logger.setLevel(level)

    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        logger.addHandler(ch)

        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(level)
            fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            fh.setFormatter(fmt)
            logger.addHandler(fh)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("doc_cleaner")
