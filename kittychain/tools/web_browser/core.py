"""Core helpers for the web_browser tool."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from urllib.parse import urlparse

_ACTIVE_SESSIONS: dict[str, float] = {}


def _run_agent_browser(session: str | None, timeout: int, *args: str) -> str:
    try:
        command = ["agent-browser"]
        if session:
            command += ["--session", session]
        completed = subprocess.run(
            [*command, *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=max(timeout, 1),
        )
    except FileNotFoundError as exc:
        raise RuntimeError("agent-browser is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip() or str(exc)
        raise RuntimeError(message) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"agent-browser command timed out after {timeout}s") from exc
    return completed.stdout.strip()


def _fetch_status_code(session: str, timeout: int) -> int | str:
    try:
        payload = _run_agent_browser(session, timeout, "--json", "network", "requests", "--type", "document")
        items = json.loads(payload)
    except Exception:
        return "unknown"
    if isinstance(items, dict):
        for key in ("requests", "items", "data"):
            value = items.get(key)
            if isinstance(value, list):
                items = value
                break
    if not isinstance(items, list):
        return "unknown"
    for item in reversed(items):
        status = item.get("status")
        if status is None:
            continue
        try:
            return int(status)
        except (TypeError, ValueError):
            return str(status)
    return "unknown"


def _close_session(session: str, timeout: int) -> None:
    try:
        subprocess.run(
            ["agent-browser", "--session", session, "close"],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(timeout, 1),
        )
    except Exception:
        return None
    return None


def _normalize_url(url: str) -> str:
    value = url.strip()
    if not value:
        raise ValueError("url is required")
    parsed = urlparse(value if "://" in value else "https://" + value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid URL: {url}")
    return parsed.geturl()


def new_session_name() -> str:
    return f"web-browser-{uuid.uuid4().hex}"


def touch_session(session: str) -> None:
    _ACTIVE_SESSIONS[session] = time.time()


def remove_session(session: str) -> None:
    _ACTIVE_SESSIONS.pop(session, None)


def cleanup_stale_sessions(max_idle_seconds: int = 600, timeout: int = 5) -> None:
    now = time.time()
    for session, last_used in list(_ACTIVE_SESSIONS.items()):
        if now - last_used <= max_idle_seconds:
            continue
        _close_session(session, timeout)
        remove_session(session)


def cleanup_all_sessions(timeout: int = 5) -> None:
    for session in list(_ACTIVE_SESSIONS.keys()):
        _close_session(session, timeout)
        remove_session(session)


def format_success(action: str, session: str | None, data=None, **extra) -> str:
    payload = {
        "success": True,
        "action": action,
        "session": session,
        "data": data if data is not None else {},
    }
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def format_error(action: str, error: str, reason: str, suggestion: str | None = None, **extra) -> str:
    payload = {
        "success": False,
        "action": action,
        "error": error,
        "reason": reason,
    }
    if suggestion:
        payload["suggestion"] = suggestion
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)
