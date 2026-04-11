"""Public web search tool."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool

_SEARCH_URL = "https://html.duckduckgo.com/html/"


class WebSearchTool(Tool):
    name = "web_search"
    description = """
Search the public web for current information and return result links with
snippets. Use this when you need fresh external sources.
    """
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to run",
            },
            "allowed_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional domains to include exclusively",
            },
            "blocked_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional domains to exclude from the results",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 20)",
            },
        },
        "required": ["query", "timeout"],
    }

    def execute(self, query: str, timeout: int = 20) -> str:
        query = query.strip()
        if len(query) < 2:
            return "Error: query must be at least 2 characters long"
        response = requests.get(_SEARCH_URL, params={"q": query}, timeout=timeout, headers={"User-Agent": "KittyChain"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for result in soup.select(".result"):
            link = result.select_one("a.result__a")
            if link is None:
                continue
            url = _unwrap_duckduckgo_url(link.get("href", ""))
            title = " ".join(link.get_text(" ", strip=True).split())
            snippet_tag = result.select_one(".result__snippet")
            snippet = " ".join(snippet_tag.get_text(" ", strip=True).split()) if snippet_tag else ""
            results.append((title, url, snippet))
            if len(results) >= 5:
                break
        if not results:
            return f'No search results found for "{query}".'
        lines = [f'Web search results for "{query}":', ""]
        for index, (title, url, snippet) in enumerate(results, 1):
            lines.append(f"{index}. {title}")
            lines.append(f"   URL: {url}")
            if snippet:
                lines.append(f"   Snippet: {snippet}")
        return "\n".join(lines)


def _unwrap_duckduckgo_url(raw_url: str) -> str:
    candidate = urljoin("https://duckduckgo.com", raw_url)
    parsed = urlparse(candidate)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        redirect_target = parse_qs(parsed.query).get("uddg")
        if redirect_target:
            return unquote(redirect_target[0])
    return candidate


def main(query: str) -> int:
    try:
        output = WebSearchTool().execute(query)
    except Exception as exc:
        output = f"Error: {exc}"
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("KittyChain"))
