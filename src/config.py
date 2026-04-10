"""KittyChain configuration loaded from ~/.kittychain/config.json."""

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".kittychain" / "config.json"


def _load_json_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


_config: dict | None = None


def get_config() -> dict:
    global _config
    if _config is None:
        _config = _load_json_config()
    return _config

_c = get_config()
DUNE_API_KEY = _c.get("dune_api_key")
GOPLUS_KEY = _c.get("goplus_api_key")
GOPLUS_SECRET = _c.get("goplus_api_secret")
ALCHEMY_API_KEY = _c.get("alchemy_api_key")
CHAINBASE_API_KEY = _c.get("chainbase_api_key")
