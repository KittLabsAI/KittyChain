"""Local skill loading from Codex skill directories."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool

SKILL_ROOTS = [
    Path.home() / ".kittychain" / "skills",
]


class SkillTool(Tool):
    name = "skill"
    description = """
Load a local skill from ~/.kittychain/skills and inject its instructions into the current run. 
Use this when one of the listed skills matches the user's request.
    """
    parameters = {
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "Skill name, for example 'commit' or 'review-pr'",
            },
            "task": {
                "type": "string",
                "description": "Optional task the selected skill should be applied to",
            },
            "args": {
                "type": "string",
                "description": "Optional free-form arguments for compatibility with slash-style skills",
            },
        },
        "required": ["skill"],
    }

    def execute(self, skill: str, task: str | None = None) -> str:
        selected = _find_skill(skill.strip())
        if selected is None:
            available = ", ".join(sorted(_list_skill_names()))
            return f'Error: unknown skill "{skill.strip()}". Available skills: {available or "(none)"}'
        body = selected.read_text(errors="replace").strip()
        lines = [f'Skill "{selected.parent.name}" selected.', f"Path: {selected}"]
        if task and task.strip():
            lines.extend(["", f"Apply to task: {task.strip()}"])
        lines.extend(["", "SKILL.md:", body])
        return "\n".join(lines)


def _list_skill_names() -> set[str]:
    names: set[str] = set()
    for root in SKILL_ROOTS:
        if not root.exists():
            continue
        for path in root.glob("*/SKILL.md"):
            names.add(path.parent.name)
    return names


def _find_skill(name: str) -> Path | None:
    normalized = name.strip().lstrip("/")
    if not normalized:
        return None
    for root in SKILL_ROOTS:
        path = root / normalized / "SKILL.md"
        if path.exists():
            return path.resolve()
    return None


def main(skill: str) -> int:
    output = SkillTool().execute(skill)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("using-superpowers"))
