"""User-facing brief status messages."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool

_VALID_STATUSES = {"normal", "proactive"}


class BriefTool(Tool):
    name = "brief"
    description = """
Send a concise user-facing message and optional local file attachments.
Use this for progress updates, blockers, or proactive status notifications.
    """
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to show the user",
            },
            "attachments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional absolute or cwd-relative file paths to attach",
            },
            "status": {
                "type": "string",
                "description": "normal for replies, proactive for unsolicited updates",
            },
        },
        "required": ["message"],
    }

    _parent_agent = None

    def execute(self, message: str, attachments: list[str] | None = None, status: str = "normal") -> str:
        text = message.strip()
        if not text:
            return "Error: message is required"
        if status not in _VALID_STATUSES:
            return f"Error: invalid status {status!r}"

        resolved = []
        for raw_path in attachments or []:
            path = Path(raw_path).expanduser().resolve()
            if not path.exists() or not path.is_file():
                return f"Error: attachment {raw_path!r} does not exist"
            resolved.append(str(path))

        payload = {"message": text, "attachments": resolved, "status": status}
        parent = self._parent_agent
        if parent is not None:
            messages = getattr(parent, "brief_messages", None)
            if messages is None:
                parent.brief_messages = []
                messages = parent.brief_messages
            messages.append(payload)
        lines = [f"Sent brief message ({status}).", text]
        if resolved:
            lines.append("Attachments:")
            lines.extend(f"- {path}" for path in resolved)
        return "\n".join(lines)


def main(message: str) -> int:
    output = BriefTool().execute(message)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("Manual brief test."))
