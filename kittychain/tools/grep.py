"""Search file contents with a regular expression."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class GrepTool(Tool):
    name = "grep"
    description = """
Search file contents with regex. Returns matching lines with file path and line number.
    """
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search (default: cwd)",
            },
            "include": {
                "type": "string",
                "description": "Only search files matching this glob (for example '*.py')",
            },
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, path: str = ".", include: str = "*") -> str:
        base = Path(path).expanduser().resolve()
        if not base.exists():
            return f"Error: {path} not found"
        regex = re.compile(pattern)
        hits = []
        for file_path in base.rglob(include):
            if not file_path.is_file():
                continue
            text = file_path.read_text(errors="replace")
            for line_no, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    hits.append(f"{file_path}:{line_no}: {line}")
        return "\n".join(hits) if hits else "No matches found."


def main(pattern: str, path: str = ".") -> int:
    output = GrepTool().execute(pattern, path=path)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("Tool", str(Path(__file__).resolve().parent)))
