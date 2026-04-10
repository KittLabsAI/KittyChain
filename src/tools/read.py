"""Read files with line numbers."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class ReadTool(Tool):
    name = "read"
    description = """
    Read a file with line numbers.
    """
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["file_path"],
    }

    def execute(self, file_path: str, offset: int = 1, limit: int = 2000) -> str:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Error: {file_path} not found"
        if not path.is_file():
            return f"Error: {file_path} is not a file"
        lines = path.read_text(errors="replace").splitlines()
        start = max(0, offset - 1)
        chunk = lines[start:start + limit]
        if not chunk:
            return "(empty file)"
        return "\n".join(f"{start + i + 1}\t{line}" for i, line in enumerate(chunk))


def main(file_path: str) -> int:
    output = ReadTool().execute(file_path)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main(str(PROJECT_ROOT / "config.py")))
