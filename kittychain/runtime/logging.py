"""Logging setup for KittyChain."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(base_dir: Path | str | None = None) -> Path:
    root_dir = Path(base_dir).expanduser() if base_dir is not None else Path.home() / ".kittychain"
    log_path = root_dir / "logs" / "kittychain.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("kittychain")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, "_kittychain_file_handler", False):
            logger.removeHandler(handler)
            handler.close()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler._kittychain_file_handler = True
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)
    return log_path
