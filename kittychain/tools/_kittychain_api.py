"""Shared KittyChain API helper."""

import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener, urlopen

import certifi
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from config import Config
else:
    from ..config import Config

KITTYCHAIN_API_BASE = "https://kittyhome.pages.dev"


class KittyChainAPIError(RuntimeError):
    pass


def _load_api_key() -> str:
    return Config.from_file().apis.kittychain_api_key


def _build_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _build_opener():
    """Build an opener that bypasses system proxy for direct HTTPS connections."""
    proxy_handler = ProxyHandler({})  # empty = no proxy
    https_handler = HTTPSHandler(context=_build_ssl_context())
    return build_opener(proxy_handler, https_handler)


def _send_request(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=headers, method="POST")
    opener = _build_opener()
    try:
        with opener.open(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise KittyChainAPIError(f"HTTP {exc.code} calling {url}: {body}") from exc
    except URLError as exc:
        raise KittyChainAPIError(f"Network error calling {url}: {exc.reason}") from exc


def post_kittychain(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    api_key = _load_api_key()
    if not api_key:
        raise KittyChainAPIError("kittychain_api_key is required")
    url = f"{KITTYCHAIN_API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "KittyChain/1.0",
        "Accept": "application/json",
    }
    result = _send_request(url, payload, headers)
    if not result.get("ok"):
        error_msg = result.get("error", "Unknown API error")
        raise KittyChainAPIError(f"KittyChain API error: {error_msg}")
    return result.get("data", {})
