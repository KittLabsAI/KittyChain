"""Sub-task delegation with a KittyChain-friendly fallback."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class AgentTool(Tool):
    name = "agent"
    description = """
Spawn a sub-agent to handle a complex sub-task independently.
The sub-agent has its own context and tool access. Use this for:
researching a codebase, implementing a multi-step change in isolation,
or any task that would benefit from a fresh context window.
    """
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "What the sub-agent should accomplish",
            },
        },
        "required": ["task"],
    }

    _parent_agent = None

    def execute(self, task: str) -> str:
        task = task.strip()
        if not task:
            return "Error: task is required"
        parent = self._parent_agent
        if parent is None:
            return "Error: agent tool requires a KittyChain parent runtime with sub-agent support"

        for attr in ("spawn_subagent", "run_subagent"):
            handler = getattr(parent, attr, None)
            if callable(handler):
                result = handler(task)
                return str(result)
        return "Error: agent tool requires a KittyChain parent runtime with sub-agent support"


def main(task: str) -> int:
    output = AgentTool().execute(task)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("Summarize the current task state."))
