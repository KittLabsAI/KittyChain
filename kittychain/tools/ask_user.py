"""Interactive user questions with safe fallback behavior."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool


class AskUserTool(Tool):
    name = "ask_user"
    description = """
Ask the user one or more questions during execution to clarify
requirements, gather preferences, or make implementation decisions.
    """
    parameters = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "description": "Questions to ask the user (1-4 items)",
                "items": {
                    "type": "object",
                    "properties": {
                        "header": {
                            "type": "string",
                            "description": "Short label for the question",
                        },
                        "question": {
                            "type": "string",
                            "description": "The full question to ask the user",
                        },
                        "multiSelect": {
                            "type": "boolean",
                            "description": "Allow selecting multiple options",
                        },
                        "allowFreeformInput": {
                            "type": "boolean",
                            "description": "Allow free-form text in addition to fixed options",
                        },
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "Display text for the option",
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Optional explanation for the option",
                                    },
                                    "recommended": {
                                        "type": "boolean",
                                        "description": "Mark the option as the recommended default",
                                    },
                                },
                                "required": ["label"],
                            },
                        },
                    },
                    "required": ["header", "question"],
                },
            }
        },
        "required": ["questions"],
    }

    _parent_agent = None

    def execute(self, questions: list[dict]) -> str:
        try:
            normalized = _normalize_questions(questions)
        except ValueError as exc:
            return f"Error: {exc}"

        handler = getattr(self._parent_agent, "ask_user_handler", None)
        if not callable(handler):
            return "Error: ask_user requires an interactive KittyChain runtime"

        answers = handler(normalized) or {}
        if not answers:
            return "User declined to answer the questions."

        lines = ["User answers:"]
        for item in normalized:
            lines.append(f"- {item['header']}: {answers.get(item['question'], '(no answer)')}")
        return "\n".join(lines)


def _normalize_questions(questions: list[dict]) -> list[dict]:
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions must contain at least one item")
    normalized = []
    for index, item in enumerate(questions, 1):
        if not isinstance(item, dict):
            raise ValueError(f"question #{index} must be an object")
        header = str(item.get("header", "")).strip()
        question = str(item.get("question", "")).strip()
        if not header or not question:
            raise ValueError(f"question #{index} must include header and question")
        normalized.append({"header": header, "question": question})
    return normalized


def main(question: str) -> int:
    output = AskUserTool().execute([{"header": "Question", "question": question}])
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("Which option should we choose?"))
