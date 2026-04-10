"""List files matching a glob pattern."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class GlobTool(Tool):
    name = "glob"
    description = """
    Find files matching a glob pattern under a directory.
    """
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, path: str = ".") -> str:
        base = Path(path).expanduser().resolve()
        if not base.exists():
            return f"Error: {path} not found"
        if not base.is_dir():
            return f"Error: {path} is not a directory"
        matches = sorted(str(item) for item in base.glob(pattern))
        return "\n".join(matches) if matches else "No files matched."


def main(pattern: str, path: str = ".") -> int:
    output = GlobTool().execute(pattern, path=path)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("*.py", str(Path(__file__).resolve().parent)))
