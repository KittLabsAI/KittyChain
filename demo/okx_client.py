from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from kittychain.config import Config

BASE_URL = "https://web3.okx.com"
DEFAULT_TIMEOUT = 20


@dataclass(frozen=True)
class OKXCredentials:
    api_key: str
    secret_key: str
    passphrase: str


def load_credentials(config: Config | None = None) -> OKXCredentials:
    apis = (config or Config.from_file()).apis
    missing = [
        field
        for field in ("okx_api_key", "okx_secret_key", "okx_passphrase")
        if not getattr(apis, field)
    ]
    if missing:
        raise ValueError(f"Missing OKX config fields: {', '.join(missing)}")
    return OKXCredentials(apis.okx_api_key, apis.okx_secret_key, apis.okx_passphrase)


def iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sign(secret_key: str, message: str) -> str:
    digest = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def build_headers(
    credentials: OKXCredentials,
    method: str,
    request_path: str,
    body: str = "",
    timestamp: str | None = None,
) -> dict[str, str]:
    timestamp = timestamp or iso_timestamp()
    method = method.upper()
    signature = sign(credentials.secret_key, f"{timestamp}{method}{request_path}{body}")
    return {
        "Content-Type": "application/json",
        "OK-ACCESS-KEY": credentials.api_key,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": credentials.passphrase,
    }


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    session: Any | None = None,
    credentials: OKXCredentials | None = None,
    timestamp: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    method = method.upper()
    credentials = credentials or load_credentials()
    session = session or requests
    query = urlencode({key: value for key, value in (params or {}).items() if value is not None})
    request_path = f"{path}?{query}" if query else path
    body = ""
    if method != "GET" and payload is not None:
        body = json.dumps(payload, separators=(",", ":"))

    headers = build_headers(credentials, method, request_path, body=body, timestamp=timestamp)
    response = session.request(
        method,
        f"{BASE_URL}{request_path}",
        headers=headers,
        data=body or None,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
