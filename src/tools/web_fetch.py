"""Fetch public web content and extract readable text."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class WebFetchTool(Tool):
    name = "web_fetch"
    description = """
    Fetch a public URL and extract readable content.
    """
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "prompt": {"type": "string"},
            "timeout": {"type": "integer"},
        },
        "required": ["url"],
    }

    def execute(self, url: str, prompt: str = "", timeout: int = 20) -> str:
        normalized = _normalize_url(url)
        response = requests.get(normalized, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        text = _extract_text(response.text, content_type)
        lines = [f"Fetched: {response.url}", f"Status: {response.status_code}", ""]
        if prompt.strip():
            lines.append(f"Prompt: {prompt.strip()}")
            lines.append("")
        lines.append(text)
        return "\n".join(lines)


def _normalize_url(url: str) -> str:
    value = url.strip()
    if not value:
        raise ValueError("url is required")
    parsed = urlparse(value if "://" in value else "https://" + value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid URL: {url}")
    return parsed.geturl()


def _extract_text(body: str, content_type: str) -> str:
    if "json" in content_type:
        try:
            return json.dumps(json.loads(body), indent=2, ensure_ascii=False)
        except Exception:
            return body
    if "html" in content_type:
        soup = BeautifulSoup(body, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return "\n".join(line for line in soup.get_text("\n").splitlines() if line.strip())
    return body


def main(url: str) -> int:
    try:
        output = WebFetchTool().execute(url)
    except Exception as exc:
        output = f"Error: {exc}"
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("https://example.com"))
