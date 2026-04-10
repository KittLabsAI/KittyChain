"""Shell command execution with basic safety checks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool

_DANGEROUS_PATTERNS = [
    (r"\brm\s+(-\w*)?-rf?\s", "dangerous delete"),
    (r"\bmkfs\b", "format filesystem"),
    (r"\bdd\s+.*of=/dev/", "raw disk write"),
]


class BashTool(Tool):
    name = "bash"
    description = """
    Execute a shell command with basic safety checks.
    """
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer"},
        },
        "required": ["command"],
    }

    def execute(self, command: str, timeout: int = 120) -> str:
        for pattern, reason in _DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return f"Error: blocked shell command ({reason})"
        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except Exception as exc:
            return f"Error: {exc}"
        lines = [f"Exit code: {completed.returncode}"]
        if completed.stdout:
            lines.extend(["STDOUT:", completed.stdout.rstrip()])
        if completed.stderr:
            lines.extend(["STDERR:", completed.stderr.rstrip()])
        return "\n".join(lines)


def main(command: str) -> int:
    output = BashTool().execute(command)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("pwd"))
