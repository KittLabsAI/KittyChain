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
Read a file's contents with line numbers. Always read a file before editing it.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 2000 lines starting from the beginning of the file
    """
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file",
            },
            "offset": {
                "type": "integer",
                "description": "Start line (1-based). Default 1.",
            },
            "limit": {
                "type": "integer",
                "description": "Max lines to read. Default 2000.",
            },
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
