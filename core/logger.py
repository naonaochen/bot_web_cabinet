from __future__ import annotations

import logging
from pathlib import Path

from .utils import project_root


def get_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    log_path = Path(log_dir)
    if not log_path.is_absolute():
        log_path = project_root() / log_path
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Rebind handlers every time so the EXE always writes to the current EXE folder.
    for handler in list(logger.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(
        log_path / "rpa.log",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logger initialized at: %s", log_path)
    return logger
