"""Multi-source social search tool with zero-key public sources."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool

_SUPPORTED_SOURCES = ("reddit", "x", "hackernews", "polymarket")
_SUPPORTED_DEPTHS = ("quick", "default", "deep")
_RESULT_LIMITS = {
    "reddit": {"quick": 10, "default": 25, "deep": 50},
    "hackernews": {"quick": 15, "default": 30, "deep": 60},
    "polymarket": {"quick": 5, "default": 15, "deep": 25},
}
_REQUEST_TIMEOUT = 20
_USER_AGENT = "KittyChain social_search/1.0"


class SocialSearchTool(Tool):
    name = "social_search"
    description = """
Search social and community sources for recent discussion about a topic.
Supports zero-key public sources first: Reddit, Hacker News, and Polymarket.
X is reported when local credentials are unavailable.
    """
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Topic or keywords to search for",
            },
            "lookback_days": {
                "type": "integer",
                "description": "How many days back to search",
            },
            "depth": {
                "type": "string",
                "enum": list(_SUPPORTED_DEPTHS),
                "description": "Search depth: quick, default, or deep",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string", "enum": list(_SUPPORTED_SOURCES)},
                "description": "Optional subset of sources to search",
            },
        },
        "required": ["query", "lookback_days", "depth"],
    }

    def execute(
        self,
        query: str,
        lookback_days: int,
        depth: str,
        sources: list[str] | None = None,
    ) -> str:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            return "Error: query must be at least 2 characters long"
        if lookback_days <= 0:
            return "Error: lookback_days must be greater than 0"
        if depth not in _SUPPORTED_DEPTHS:
            return f"Error: depth must be one of {', '.join(_SUPPORTED_DEPTHS)}"

        requested_sources = _normalize_sources(sources)
        from_date, to_date = _date_range(lookback_days)

        results: dict[str, list[dict[str, Any]]] = {}
        statuses: dict[str, str] = {}
        for source in requested_sources:
            if source == "reddit":
                items = _search_reddit(normalized_query, lookback_days, depth)
                results[source] = items
                statuses[source] = f"{len(items)} result" if len(items) == 1 else f"{len(items)} results"
                continue
            if source == "hackernews":
                items = _search_hackernews(normalized_query, lookback_days, depth)
                results[source] = items
                statuses[source] = f"{len(items)} result" if len(items) == 1 else f"{len(items)} results"
                continue
            if source == "polymarket":
                items = _search_polymarket(normalized_query, lookback_days, depth)
                results[source] = items
                statuses[source] = f"{len(items)} result" if len(items) == 1 else f"{len(items)} results"
                continue
            if source == "x":
                x_result = _search_x(normalized_query, lookback_days, depth)
                results[source] = x_result["items"]
                if x_result["available"]:
                    count = len(x_result["items"])
                    statuses[source] = f"{count} result" if count == 1 else f"{count} results"
                else:
                    statuses[source] = f"unavailable ({x_result['reason']})"

        lines = [
            f'Social search results for "{normalized_query}"',
            f"Window: last {lookback_days} days ({from_date} to {to_date})",
            f"Depth: {depth}",
            "",
            "Source summary:",
        ]
        for source in requested_sources:
            lines.append(f"- {source}: {statuses[source]}")

        flattened = [
            (source, item)
            for source in requested_sources
            for item in results.get(source, [])
        ]
        if not flattened:
            lines.extend(["", "No results found."])
            return "\n".join(lines)

        lines.extend(["", "Top results:"])
        for index, (source, item) in enumerate(flattened[:12], start=1):
            title = str(item.get("title") or "(untitled)").strip()
            url = str(item.get("url") or item.get("hn_url") or "").strip()
            meta = _format_item_meta(source, item)
            lines.append(f"{index}. [{source}] {title}")
            if url:
                lines.append(f"   URL: {url}")
            if meta:
                lines.append(f"   Meta: {meta}")
        return "\n".join(lines)


def _normalize_sources(sources: list[str] | None) -> list[str]:
    if not sources:
        return list(_SUPPORTED_SOURCES)
    normalized: list[str] = []
    for raw in sources:
        source = raw.strip().lower()
        if source not in _SUPPORTED_SOURCES:
            raise ValueError(f"Unsupported source: {raw}")
        if source not in normalized:
            normalized.append(source)
    if not normalized:
        raise ValueError("At least one source is required")
    return normalized


def _date_range(lookback_days: int) -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=lookback_days)
    return start.isoformat(), today.isoformat()


def _request_json(url: str, *, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(
        url,
        params=params,
        timeout=_REQUEST_TIMEOUT,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def _search_reddit(query: str, lookback_days: int, depth: str) -> list[dict[str, Any]]:
    del lookback_days
    limit = _RESULT_LIMITS["reddit"][depth]
    payload = _request_json(
        "https://www.reddit.com/search.json",
        params={
            "q": query,
            "sort": "relevance",
            "t": "month",
            "limit": limit,
            "raw_json": 1,
        },
    )
    children = payload.get("data", {}).get("children", [])
    items: list[dict[str, Any]] = []
    for child in children:
        post = child.get("data", {})
        permalink = str(post.get("permalink") or "").strip()
        if not permalink:
            continue
        created = post.get("created_utc")
        published = None
        if created:
            published = datetime.fromtimestamp(float(created), tz=timezone.utc).date().isoformat()
        items.append(
            {
                "title": str(post.get("title") or "").strip(),
                "url": f"https://www.reddit.com{permalink}",
                "published_at": published,
                "engagement": {
                    "score": int(post.get("score") or 0),
                    "comments": int(post.get("num_comments") or 0),
                },
                "subreddit": str(post.get("subreddit") or "").strip(),
            }
        )
    return items[:limit]


def _search_hackernews(query: str, lookback_days: int, depth: str) -> list[dict[str, Any]]:
    limit = _RESULT_LIMITS["hackernews"][depth]
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp())
    payload = _request_json(
        "https://hn.algolia.com/api/v1/search",
        params={
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{start_ts}",
            "hitsPerPage": limit,
        },
    )
    hits = payload.get("hits", [])
    items: list[dict[str, Any]] = []
    for hit in hits:
        url = str(hit.get("url") or "").strip()
        object_id = str(hit.get("objectID") or "").strip()
        if not url and object_id:
            url = f"https://news.ycombinator.com/item?id={object_id}"
        items.append(
            {
                "title": str(hit.get("title") or "").strip(),
                "url": url,
                "hn_url": f"https://news.ycombinator.com/item?id={object_id}" if object_id else "",
                "published_at": _iso_from_unix(hit.get("created_at_i")),
                "engagement": {
                    "points": int(hit.get("points") or 0),
                    "comments": int(hit.get("num_comments") or 0),
                },
                "author": str(hit.get("author") or "").strip(),
            }
        )
    return items[:limit]


def _search_polymarket(query: str, lookback_days: int, depth: str) -> list[dict[str, Any]]:
    del lookback_days
    pages = {"quick": 1, "default": 2, "deep": 3}[depth]
    limit = _RESULT_LIMITS["polymarket"][depth]
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        payload = _request_json(
            "https://gamma-api.polymarket.com/public-search",
            params={
                "q": query,
                "page": page,
                "events_status": "active",
                "keep_closed_markets": 0,
            },
        )
        page_events = payload.get("events") if isinstance(payload, dict) else payload
        if not isinstance(page_events, list):
            continue
        for event in page_events:
            slug = str(event.get("slug") or "").strip()
            title = str(event.get("title") or event.get("name") or "").strip()
            if not title:
                continue
            dedupe_key = slug or title.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            events.append(
                {
                    "title": title,
                    "url": f"https://polymarket.com/event/{slug}" if slug else "",
                    "published_at": str(event.get("endDate") or event.get("createdAt") or "").strip()[:10] or None,
                    "engagement": {
                        "volume": event.get("volume"),
                        "liquidity": event.get("liquidity"),
                    },
                }
            )
            if len(events) >= limit:
                return events
    return events[:limit]


def _search_x(query: str, lookback_days: int, depth: str) -> dict[str, Any]:
    del query, lookback_days, depth
    if not os.environ.get("AUTH_TOKEN") or not os.environ.get("CT0"):
        return {
            "available": False,
            "items": [],
            "reason": "AUTH_TOKEN/CT0 not configured",
        }
    if shutil.which("bird") is None:
        return {
            "available": False,
            "items": [],
            "reason": "bird command not installed",
        }
    return {
        "available": False,
        "items": [],
        "reason": "local X search bridge not implemented",
    }


def _iso_from_unix(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _format_item_meta(source: str, item: dict[str, Any]) -> str:
    parts: list[str] = []
    published = item.get("published_at")
    if published:
        parts.append(str(published))
    if source == "reddit":
        subreddit = item.get("subreddit")
        if subreddit:
            parts.append(f"r/{subreddit}")
        engagement = item.get("engagement") or {}
        parts.append(f"score {engagement.get('score', 0)}")
        parts.append(f"comments {engagement.get('comments', 0)}")
    elif source == "hackernews":
        engagement = item.get("engagement") or {}
        parts.append(f"points {engagement.get('points', 0)}")
        parts.append(f"comments {engagement.get('comments', 0)}")
    elif source == "polymarket":
        engagement = item.get("engagement") or {}
        if engagement.get("volume") not in (None, ""):
            parts.append(f"volume {engagement['volume']}")
        if engagement.get("liquidity") not in (None, ""):
            parts.append(f"liquidity {engagement['liquidity']}")
    return " | ".join(parts)


def main(query: str) -> int:
    try:
        output = SocialSearchTool().execute(query=query, lookback_days=30, depth="default")
    except Exception as exc:
        output = f"Error: {exc}"
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("KittyChain"))
