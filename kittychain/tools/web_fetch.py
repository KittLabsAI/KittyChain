"""Fetch public web content and extract readable text."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# Browser-like headers to bypass anti-bot detection
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class WebFetchTool(Tool):
    name = "web_fetch"
    description = """
Fetch content from a public URL, extract readable text, and summarize it
against a prompt. Use this to inspect current web pages or text endpoints.
# Important Notes
- Always use this after calling other tools like address_malicious to verify their results by fetching relevant web pages.
- `https://www.oklink.com/` for addresses, transactions, and token information by token address.
- `https://www.blockchain.com/explorer` use when oklink is unavailable.
- `https://solscan.io/` for Solana addresses and transactions.
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
                "description": "Timeout in seconds (default 20)",
            },
        },
        "required": ["url", "prompt", "timeout"],
    }

    def execute(self, url: str, prompt: str = "", timeout: int = 20) -> str:
        normalized = _normalize_url(url)
        headers = _BROWSER_HEADERS.copy()
        # Rotate User-Agent to appear more human-like
        if random.random() > 0.5:
            browsers = [
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
            headers["User-Agent"] = random.choice(browsers)
        response = requests.get(normalized, headers=headers, timeout=timeout)
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
