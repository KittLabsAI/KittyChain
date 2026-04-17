"""Shell command execution with basic safety checks."""

from __future__ import annotations

import re
import shlex
import subprocess
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

_DANGEROUS_PATTERNS = [
    (r"\brm\s+(-\w*)?-r\w*\s+(/|~|\$HOME)", "recursive delete on home/root"),
    (r"\brm\s+(-\w*)?-rf\s", "force recursive delete"),
    (r"\bmkfs\b", "format filesystem"),
    (r"\bdd\s+.*of=/dev/", "raw disk write"),
    (r">\s*/dev/sd[a-z]", "overwrite block device"),
    (r"\bchmod\s+(-R\s+)?777\s+/", "chmod 777 on root"),
    (r":\(\)\s*\{.*:\|:.*\}", "fork bomb"),
    (r"\bcurl\b.*\|\s*(sudo\s+)?bash", "pipe curl to bash"),
    (r"\bwget\b.*\|\s*(sudo\s+)?bash", "pipe wget to bash"),
]

_AVOID_COMMANDS = [
    "cat", "head", "tail", "sed", "awk", "echo",
    "find", "grep", "cat", "head", "tail", "sed", "awk", "echo"
]

_PERMISSION_WHITELIST = {
    "agent-browser",
    "curl"
}


class BashTool(Tool):
    name = "bash"
    description = f"""
Execute a shell command. Returns stdout, stderr, and exit code.
Use this for running tests, installing packages, git operations, and similar tasks.
The working directory persists between commands, but shell state does not. The shell environment is initialized from the user's profile (bash or zsh).
IMPORTANT: Avoid using this tool to run {', '.join(_AVOID_COMMANDS)} commands, unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. Instead, use the appropriate dedicated tool as this will provide a much better experience for the user.
File search: Use glob tool (NOT find or ls)
Content search: Use grep tool (NOT grep or rg)
Read files: Use read_file tool (NOT cat/head/tail)
Edit files: Use edit_file tool (NOT sed/awk)
Write files: Use write_file tool (NOT echo >/cat <<EOF)
Communication: Output text directly (NOT echo/printf)
If your command will create new directories or files, first use this tool to run `ls` to verify the parent directory exists and is the correct location.
Always quote file paths that contain spaces with double quotes in your command (e.g., cd "path with spaces/file.txt")
Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.
    """
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to run",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 120)",
            },
        },
        "required": ["command"],
    }

    def execute(self, command: str, timeout: int = 120) -> str:
        for pattern, reason in _DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return f"Error: blocked shell command ({reason})"
        agent = getattr(self, "_parent_agent", None)
        if agent is not None and not _is_permission_whitelisted(command):
            try:
                decision = request_user_permission(
                    agent,
                    description=f"Allow the agent to run this shell command?\n\n{command}",
                    options=[
                        {"label": "Allow", "value": "allow"},
                        {"label": "Deny", "value": "deny"},
                    ],
                    title="Bash Permission",
                )
            except (RuntimeError, ValueError) as exc:
                return f"Error: {exc}"
            if decision != "allow":
                return "User denied permission grant"
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


def _is_permission_whitelisted(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return bool(parts) and parts[0] in _PERMISSION_WHITELIST


def main(command: str) -> int:
    output = BashTool().execute(command)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("pwd"))
