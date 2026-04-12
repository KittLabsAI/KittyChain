"""Fetch public web content through agent-browser and extract readable text."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class WebBrowserTool(Tool):
    name = "web_browser"
    description = """
Fetch content from a public URL through a real browser, extract readable text, and summarize it
against a prompt. Use this to inspect current web pages or text endpoints.

# Important Notes
- ALWAYS use this after calling other tools like address_malicious to verify their results by fetching relevant web pages.
- If this tool is unavailable or fails, use `agent-browser` tool.
- ALWAYS try to get relevant counterparties or entities from webpage.
- After calling this tool, if find relevant addresses, ALWAYS check the 3-5 most frequently interacting addresses with `address_malicious` and `web_browser`.
- If timeout, try again with a longer timeout.

# Important Webpage
- `https://www.oklink.com/` or `https://www.blockchain.com/explorer` for all public chains.
- `https://etherscan.io/` for Ethereum-compatible chains.
- `https://solscan.io/` for Solana.
- `https://suiscan.xyz/mainnet/home` or `https://sui.explorers.guru/` for Sui.
- `https://coinmarketcap.com/` for market information.
- `https://tokenvitals.com/` for token information by token name.
    """
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch",
            },
            "prompt": {
                "type": "string",
                "description": "What information to extract from the fetched content",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 120)",
            },
        },
        "required": ["url", "prompt", "timeout"],
    }

    def execute(self, url: str, prompt: str = "", timeout: int = 20) -> str:
        normalized = _normalize_url(url)
        session = f"web-browser-{uuid.uuid4().hex}"
        try:
            _run_agent_browser(session, timeout, "open", normalized)
            _run_agent_browser(session, timeout, "wait", "--load", "networkidle")
            current_url = _run_agent_browser(session, timeout, "get", "url")
            text = _run_agent_browser(
                session,
                timeout,
                "eval",
                "document.body ? (document.body.innerText || '') : "
                "(document.documentElement ? (document.documentElement.innerText || '') : '')",
            )
            status_code = _fetch_status_code(session, timeout)
        finally:
            _close_session(session, timeout)
        lines = [f"Fetched: {current_url or normalized}", f"Status: {status_code}", ""]
        if prompt.strip():
            lines.append(f"Prompt: {prompt.strip()}")
            lines.append("")
        lines.append(text.strip())
        return "\n".join(lines)


def _run_agent_browser(session: str, timeout: int, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["agent-browser", "--session", session, *args],
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


def main(url: str) -> int:
    try:
        output = WebBrowserTool().execute(url)
    except Exception as exc:
        output = f"Error: {exc}"
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("https://example.com"))
