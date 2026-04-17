"""Fetch public web content through agent-browser and extract readable text."""

import time

from .core import (
    _ACTIVE_SESSIONS,
    _close_session,
    _fetch_status_code,
    _normalize_url,
    _run_agent_browser,
    json,
    remove_session,
    subprocess,
    touch_session,
)
from .summarize import _summarize_with_llm
from .tool import WebBrowserTool, main


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


__all__ = [
    "WebBrowserTool",
    "main",
    "subprocess",
    "json",
    "_ACTIVE_SESSIONS",
    "_run_agent_browser",
    "_fetch_status_code",
    "_close_session",
    "_normalize_url",
    "touch_session",
    "remove_session",
    "cleanup_stale_sessions",
    "cleanup_all_sessions",
    "_summarize_with_llm",
]
