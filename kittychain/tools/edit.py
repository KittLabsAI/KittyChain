"""Exact-string file editing."""

import difflib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class EditTool(Tool):
    name = "edit"
    description = """
Edit a file by replacing an exact string match.
old_string must appear exactly once in the file for safety.
Include enough surrounding context to ensure uniqueness.
    """
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to find (must be unique in file)",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }

    def execute(self, file_path: str, old_string: str, new_string: str) -> str:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Error: {file_path} not found"
        content = path.read_text()
        count = content.count(old_string)
        if count == 0:
            return f"Error: old_string not found in {file_path}"
        if count > 1:
            return f"Error: old_string appears {count} times in {file_path}"
        new_content = content.replace(old_string, new_string, 1)
        path.write_text(new_content)
        diff = "".join(
            difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=1,
            )
        )
        return f"Edited {file_path}\n{diff}".rstrip()


def main(file_path: str, old_string: str = "old", new_string: str = "new") -> int:
    output = EditTool().execute(file_path, old_string, new_string)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("/tmp/kittychain-edit-test.txt"))
