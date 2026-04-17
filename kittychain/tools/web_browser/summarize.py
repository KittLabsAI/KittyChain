"""LLM summarization helpers for web_browser."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from llm.provider import _strip_think_blocks  # type: ignore
else:
    from ...llm.provider import _strip_think_blocks


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
    response = worker.complete(
        [message],
        system=(
            "Return a brief summary of the page that answers the prompt, "
            "followed by a brief next-step suggestion."
        ),
    )
    return _strip_think_blocks((response.content or "").strip())
