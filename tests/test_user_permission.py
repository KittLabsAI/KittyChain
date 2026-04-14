import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import kittychain.cli as cli
import kittychain.tools.edit as edit_module
import kittychain.tools.write as write_module
from kittychain.hooks.user_permission import request_user_permission


def test_request_user_permission_returns_selected_value():
    captured = {}

    def handler(payload):
        captured["payload"] = payload
        return "allow"

    agent = SimpleNamespace(permission_handler=handler)

    result = request_user_permission(
        agent,
        description="Allow overwriting /tmp/demo.txt?",
        options=[
            {"label": "Allow", "value": "allow"},
            {"label": "Deny", "value": "deny"},
        ],
    )

    assert result == "allow"
    assert captured["payload"]["description"] == "Allow overwriting /tmp/demo.txt?"
    assert captured["payload"]["options"] == [
        {"label": "Allow", "value": "allow"},
        {"label": "Deny", "value": "deny"},
    ]


def test_request_user_permission_requires_runtime_handler():
    agent = SimpleNamespace(permission_handler=None)

    with pytest.raises(RuntimeError, match="interactive KittyChain runtime"):
        request_user_permission(
            agent,
            description="Allow writing?",
            options=[{"label": "Allow", "value": "allow"}],
        )


def test_readline_input_select_option_returns_choice_and_clears_modal(tmp_path):
    history_path = tmp_path / "history.txt"
    reader = cli._ReadlineInput(str(history_path), lambda: [])
    reader._ui_thread = threading.current_thread()
    reader._call_in_ui_thread = lambda func, wait=False: func()

    selected = {}

    worker = threading.Thread(
        target=lambda: selected.setdefault(
            "value",
            reader.select_option(
                title="File Permission",
                description="Allow the write?",
                options=[
                    {"label": "Allow", "value": "allow"},
                    {"label": "Deny", "value": "deny"},
                ],
            ),
        ),
        daemon=True,
    )
    worker.start()

    deadline = time.time() + 2
    while reader._permission_modal is None and time.time() < deadline:
        time.sleep(0.01)

    assert reader._permission_modal is not None
    reader._move_permission_selection_ui(1)
    reader._confirm_permission_selection_ui()
    worker.join(timeout=2)

    assert selected["value"] == "deny"
    assert reader._permission_modal is None


def test_readline_input_select_option_focuses_permission_modal(tmp_path):
    history_path = tmp_path / "history.txt"
    reader = cli._ReadlineInput(str(history_path), lambda: [])
    reader._ui_thread = threading.current_thread()
    reader._call_in_ui_thread = lambda func, wait=False: func()

    worker = threading.Thread(
        target=lambda: reader.select_option(
            title="File Permission",
            description="Allow the write?",
            options=[
                {"label": "Allow", "value": "allow"},
                {"label": "Deny", "value": "deny"},
            ],
        ),
        daemon=True,
    )
    worker.start()

    deadline = time.time() + 2
    while reader._permission_modal is None and time.time() < deadline:
        time.sleep(0.01)

    assert reader._permission_modal is not None
    assert reader.layout.current_control == reader._permission_modal_window.content

    reader._confirm_permission_selection_ui()
    worker.join(timeout=2)


def test_permission_modal_uses_full_overlay_for_centering(tmp_path):
    reader = cli._ReadlineInput(str(tmp_path / "history.txt"), lambda: [])

    overlay_float = reader.layout.container.floats[1]

    assert overlay_float.top == 0
    assert overlay_float.bottom == 0
    assert overlay_float.left == 0
    assert overlay_float.right == 0


def test_permission_modal_renderer_works_when_modal_is_active(tmp_path):
    history_path = tmp_path / "history.txt"
    reader = cli._ReadlineInput(str(history_path), lambda: [])
    reader._permission_modal = cli._PermissionModalState(
        title="File Permission",
        description="Allow the agent to write reports/demo.txt?",
        options=[
            {"label": "Allow", "value": "allow"},
            {"label": "Deny", "value": "deny"},
        ],
        selected_index=0,
        done=threading.Event(),
        result={"value": None},
    )

    fragments = reader._render_permission_modal_fragments()

    rendered = "".join(text for _style, text in fragments)
    assert "File Permission" in rendered
    assert "Allow" in rendered
    assert "Deny" in rendered


def test_write_tool_returns_denied_without_writing_file(tmp_path):
    path = tmp_path / "note.txt"
    tool = write_module.WriteTool()
    tool.bind_agent(SimpleNamespace(permission_handler=lambda payload: "deny"))

    result = tool.execute(str(path), "hello")

    assert result == "User denied permission grant"
    assert not path.exists()


def test_write_tool_writes_after_user_approves(tmp_path):
    path = tmp_path / "note.txt"
    tool = write_module.WriteTool()
    tool.bind_agent(SimpleNamespace(permission_handler=lambda payload: "allow"))

    result = tool.execute(str(path), "hello")

    assert result == f"Wrote {path}"
    assert path.read_text() == "hello"


def test_edit_tool_returns_denied_without_mutating_file(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("before hello after")
    tool = edit_module.EditTool()
    tool.bind_agent(SimpleNamespace(permission_handler=lambda payload: "deny"))

    result = tool.execute(str(path), "hello", "goodbye")

    assert result == "User denied permission grant"
    assert path.read_text() == "before hello after"


def test_edit_tool_writes_after_user_approves(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("before hello after")
    tool = edit_module.EditTool()
    tool.bind_agent(SimpleNamespace(permission_handler=lambda payload: "allow"))

    result = tool.execute(str(path), "hello", "goodbye")

    assert result.startswith(f"Edited {path}")
    assert path.read_text() == "before goodbye after"
