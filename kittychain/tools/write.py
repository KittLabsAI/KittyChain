"""Write full file contents."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from hooks.user_permission import request_user_permission  # type: ignore
else:
    from .base import Tool
    from ..hooks.user_permission import request_user_permission


class WriteTool(Tool):
    name = "write"
    description = """
Create a new file or completely overwrite an existing one.
If this is an existing file, you MUST use the read_file tool first to read the file's contents. This tool will fail if you did not read the file first.
For small edits to existing files, prefer the edit_file tool instead.
    """
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path for the file",
            },
            "content": {
                "type": "string",
                "description": "Full file content to write",
            },
        },
        "required": ["file_path", "content"],
    }

    def execute(self, file_path: str, content: str) -> str:
        path = Path(file_path).expanduser().resolve()
        agent = getattr(self, "_parent_agent", None)
        if agent is not None:
            try:
                decision = request_user_permission(
                    agent,
                    description=f"Allow the agent to write {path}?",
                    options=[
                        {"label": "Allow", "value": "allow"},
                        {"label": "Deny", "value": "deny"},
                    ],
                    title="File Permission",
                )
            except (RuntimeError, ValueError) as exc:
                return f"Error: {exc}"
            if decision != "allow":
                return "User denied permission grant"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Wrote {file_path}"


def main(file_path: str, content: str = "sample") -> int:
    output = WriteTool().execute(file_path, content)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("/tmp/kittychain-write-test.txt", "hello"))
