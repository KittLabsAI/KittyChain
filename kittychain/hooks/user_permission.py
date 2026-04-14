"""Interactive permission selection hook."""

from __future__ import annotations


def request_user_permission(
    agent,
    description: str,
    options: list[dict[str, str]],
    title: str = "Permission Required",
):
    handler = getattr(agent, "permission_handler", None)
    if not callable(handler):
        raise RuntimeError("user_permission requires an interactive KittyChain runtime")

    if not isinstance(options, list) or not options:
        raise ValueError("options must contain at least one item")

    normalized_options: list[dict[str, str]] = []
    for index, item in enumerate(options, 1):
        if not isinstance(item, dict):
            raise ValueError(f"option #{index} must be an object")
        label = str(item.get("label", "")).strip()
        value = str(item.get("value", label)).strip()
        if not label or not value:
            raise ValueError(f"option #{index} must include label and value")
        normalized_options.append({"label": label, "value": value})

    payload = {
        "title": str(title).strip() or "Permission Required",
        "description": str(description).strip(),
        "options": normalized_options,
    }
    return handler(payload)
