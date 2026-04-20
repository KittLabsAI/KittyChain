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
    from llm.provider import _strip_think_blocks  # type: ignore
else:
    from .base import Tool
    from ..llm.provider import _strip_think_blocks


_SUMMARY_SYSTEM_PROMPT = (
    "Return a brief summary of the page that directly answers the prompt, "
    "then add one brief next-step suggestion. "
    "If the page appears blocked or cannot be meaningfully retrieved because of bot or security detection, "
    "say so plainly and suggest using the `agent-browser` skill instead."
)

_SECURITY_MARKERS = (
    "access denied",
    "attention required",
    "captcha",
    "cf-chl",
    "cloudflare",
    "security check",
    "verify you are human",
    "bot detection",
)


class WebFetchTool(Tool):
    name = "web_fetch"
    description = """
Fetch content from a public URL, extract readable text, and summarize it
against a prompt. Use this to inspect current web pages or text endpoints.

# Important Notes
- Always use this after calling other tools like address_malicious to verify their results by fetching relevant web pages.
- If unable to find information through this tool, use `agent-browser` skill to interact with the web page in a more flexible way.
- ALWAYS try to get relevant counterparties or entities from webpage.
- After calling this tool, if find relevant addresses, ALWAYS check the 3-5 most frequently interacting addresses with `address_malicious` and `web_fetch`.
- If timeout, try again with a longer timeout.

# Important Webpage
- https://www.oklink.com/, https://tokenview.io/, https://blockchair.com/, or https://www.blockchain.com/explorer for multiple public chains.
- https://etherscan.io/, https://bscscan.com/, https://arbiscan.io/, https://basescan.org/, https://blockscan.com/, or https://www.blockscout.com/ for Ethereum-compatible chains.
- https://solscan.io/ or https://explorer.solana.com/ for Solana.
- https://tronscan.org/ for TRON.
- https://mempool.space/ for Bitcoin.
- https://www.mintscan.io/ for Cosmos ecosystem chains.
- https://suiscan.xyz/mainnet/home or https://sui.explorers.guru/ for Sui.
- https://coinmarketcap.com/ for market information.
- https://tokenvitals.com/ for token information by token name.
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
        try:
            response = requests.get(normalized, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            return f"Error: {exc}"

        content_type = response.headers.get("Content-Type", "").lower()
        text = _extract_text(response.text, content_type)
        if _looks_like_security_detection(response.status_code, text):
            return _summarize_with_llm(self._parent_agent, response.url, response.status_code, prompt, text)

        response.raise_for_status()
        return _summarize_with_llm(self._parent_agent, response.url, response.status_code, prompt, text)


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


def _looks_like_security_detection(status_code: int, page_text: str) -> bool:
    lowered = (page_text or "").lower()
    if status_code in {403, 429, 503}:
        return True
    return any(marker in lowered for marker in _SECURITY_MARKERS)


def _summarize_with_llm(agent, url: str, status_code: int | str, prompt: str, page_text: str) -> str:
    llm = getattr(agent, "llm", None)
    if llm is None or not hasattr(llm, "complete"):
        lines = [f"Fetched: {url}", f"Status: {status_code}", ""]
        if prompt.strip():
            lines.append(f"Prompt: {prompt.strip()}")
            lines.append("")
        lines.append(page_text.strip())
        return "\n".join(lines)

    worker = llm.clone() if hasattr(llm, "clone") else llm
    message = {
        "role": "user",
        "content": (
            f"Prompt:\n{prompt.strip() or 'Summarize the page content.'}\n\n"
            f"Fetched URL: {url}\n"
            f"Status: {status_code}\n\n"
            f"Page content:\n{page_text.strip()}"
        ),
    }
    response = worker.complete([message], system=_SUMMARY_SYSTEM_PROMPT)
    summary = _strip_think_blocks((response.content or "").strip())
    if summary:
        return summary
    lines = [f"Fetched: {url}", f"Status: {status_code}", ""]
    if prompt.strip():
        lines.append(f"Prompt: {prompt.strip()}")
        lines.append("")
    lines.append(page_text.strip())
    return "\n".join(lines)


def main(url: str) -> int:
    try:
        output = WebFetchTool().execute(url)
    except Exception as exc:
        output = f"Error: {exc}"
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("https://example.com"))
