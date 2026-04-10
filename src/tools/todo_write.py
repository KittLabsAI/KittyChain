"""Session todo tracking with a safe fallback store."""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool

_VALID_STATUSES = {"pending", "in_progress", "completed"}


class TodoWriteTool(Tool):
    name = "todo_write"
    description = """
    Replace the current session todo list with structured task entries.
    """
    parameters = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "active_form": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": ["content", "active_form", "status"],
                },
            }
        },
        "required": ["todos"],
    }

    _parent_agent = None

    def execute(self, todos: list[dict]) -> str:
        try:
            normalized = _normalize_todos(todos)
        except ValueError as exc:
            return f"Error: {exc}"
        parent = self._parent_agent
        if parent is not None:
            parent.todos = deepcopy(normalized)
        else:
            self._todos = deepcopy(normalized)
        lines = ["Updated todo list:"]
        lines.extend(f"- [{item['status']}] {item['content']}" for item in normalized)
        return "\n".join(lines)


def _normalize_todos(todos: list[dict]) -> list[dict]:
    if not isinstance(todos, list) or not todos:
        raise ValueError("todos must contain at least one item")
    normalized = []
    for index, item in enumerate(todos, 1):
        if not isinstance(item, dict):
            raise ValueError(f"todo #{index} must be an object")
        content = str(item.get("content", "")).strip()
        active_form = str(item.get("active_form", "")).strip()
        status = str(item.get("status", "")).strip()
        if not content or not active_form:
            raise ValueError(f"todo #{index} must include content and active_form")
        if status not in _VALID_STATUSES:
            raise ValueError(f"todo #{index} has invalid status {status!r}")
        normalized.append({"content": content, "active_form": active_form, "status": status})
    return normalized


def main() -> int:
    output = TodoWriteTool().execute(
        [{"content": "Run sample task", "active_form": "Running sample task", "status": "in_progress"}]
    )
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main())
