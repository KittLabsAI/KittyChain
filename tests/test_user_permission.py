import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

import kittychain.cli as cli
import kittychain.tools.bash as bash_module
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


def test_permission_modal_mouse_wheel_scrolls_long_description(tmp_path):
    history_path = tmp_path / "history.txt"
    reader = cli._ReadlineInput(str(history_path), lambda: [])
    reader._permission_modal = cli._PermissionModalState(
        title="File Permission",
        description="\n".join(f"line {index}" for index in range(1, 41)),
        options=[
            {"label": "Allow", "value": "allow"},
            {"label": "Deny", "value": "deny"},
        ],
        selected_index=0,
        done=threading.Event(),
        result={"value": None},
    )

    before = "".join(text for _style, text in reader._render_permission_modal_fragments())

    with set_app(reader.application):
        reader._permission_modal_window.content.mouse_handler(
            MouseEvent(Point(x=0, y=0), MouseEventType.SCROLL_DOWN, MouseButton.LEFT, frozenset())
        )

    after = "".join(text for _style, text in reader._render_permission_modal_fragments())

    assert before != after
    assert "line 1" in before
    assert "line 1" not in after
    assert "line 40" not in after


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


def test_bash_tool_returns_denied_without_running_command(monkeypatch):
    called = {"value": False}
    tool = bash_module.BashTool()
    tool.bind_agent(SimpleNamespace(permission_handler=lambda payload: "deny"))

    def fake_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("bash command should not run when permission is denied")

    monkeypatch.setattr(bash_module.subprocess, "run", fake_run)

    result = tool.execute("pwd")

    assert result == "User denied permission grant"
    assert called["value"] is False


def test_bash_tool_runs_after_user_approves(monkeypatch):
    tool = bash_module.BashTool()
    tool.bind_agent(SimpleNamespace(permission_handler=lambda payload: "allow"))

    class FakeCompleted:
        returncode = 0
        stdout = "/tmp\n"
        stderr = ""

    monkeypatch.setattr(bash_module.subprocess, "run", lambda *args, **kwargs: FakeCompleted())

    result = tool.execute("pwd")

    assert "Exit code: 0" in result
    assert "/tmp" in result


def test_bash_tool_whitelisted_agent_browser_command_skips_permission(monkeypatch):
    permission_called = {"value": False}
    tool = bash_module.BashTool()
    tool.bind_agent(
        SimpleNamespace(
            permission_handler=lambda payload: permission_called.__setitem__("value", True) or "deny"
        )
    )

    class FakeCompleted:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setattr(bash_module.subprocess, "run", lambda *args, **kwargs: FakeCompleted())

    result = tool.execute("agent-browser open https://example.com")

    assert "Exit code: 0" in result
    assert "ok" in result
    assert permission_called["value"] is False
