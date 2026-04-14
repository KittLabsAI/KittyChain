from pathlib import Path
from types import SimpleNamespace

from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.processors import TransformationInput
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

import kittychain.cli as cli
import kittychain.llm.provider as provider
import kittychain.prompt.builder as prompt_builder
import kittychain.runtime.agent as agent_module
from kittychain.llm.provider import ToolCall
import kittychain.skills.discovery as skill_discovery
import kittychain.tools.skill as skill_tool
from kittychain import Agent, Config, LLM
from kittychain.main import main


def test_kittychain_package_exports_runtime_surface():
    assert Agent is not None
    assert Config is not None
    assert LLM is not None


def test_main_module_exports_main():
    assert callable(main)


def test_skill_block_default_directory_uses_kittychain_home():
    assert skill_discovery.SKILLS_DIR == Path.home() / ".kittychain" / "skills"


def test_skill_tool_roots_use_kittychain_home():
    assert skill_tool.SKILL_ROOTS == [Path.home() / ".kittychain" / "skills"]


def test_system_prompt_includes_skills_and_user_prompt_omits_empty_todo():
    skill = SimpleNamespace(name="using-superpowers", description="Required startup skill", path="/tmp/skill.md")
    tool = SimpleNamespace(name="demo_tool", description="Demo tool")

    system = prompt_builder.system_prompt([tool], skills=[skill])
    user = prompt_builder.user_prompt("hello")

    assert "# Skills" in system
    assert "using-superpowers" in system
    assert "<system-reminder>" not in user
    assert "<todo-reminder>" not in user


def test_system_prompt_mentions_optional_system_reminder_tag_and_user_prompt_includes_it_for_deep_mode():
    tool = SimpleNamespace(name="demo_tool", description="Demo tool")

    system = prompt_builder.system_prompt([tool])
    user = prompt_builder.user_prompt("hello", mode="deep")

    assert "<system-reminder>" in system
    assert "<system-reminder>" in user
    assert "深度调查模式已开启" in user
    assert "一层/二层交易对手地址信息" in user


def test_system_prompt_describes_onchain_risk_analysis_role():
    tool = SimpleNamespace(name="demo_tool", description="Demo tool")

    system = prompt_builder.system_prompt([tool])

    assert "You are KittyChain, an AI on-chain risk analysis assistant running in the user's terminal." in system
    assert "You help with on-chain risk analysis" in system


def test_system_prompt_includes_onchain_lookup_rules():
    tool = SimpleNamespace(name="demo_tool", description="Demo tool")

    system = prompt_builder.system_prompt([tool])

    assert "# On-chain lookup checks" in system
    assert "address_pattern" in system
    assert "address_malicious" in system
    assert "address_transfers" in system
    assert "address_identity" in system
    assert "token_holders" in system
    assert "https://www.oklink.com/" in system
    assert "web_search` and the `social_search` tool" in system


def test_system_prompt_includes_user_facing_output_rules():
    tool = SimpleNamespace(name="demo_tool", description="Demo tool")

    system = prompt_builder.system_prompt([tool])

    assert "# When presenting results to the user" in system
    assert "full address instead of an abbreviated form" in system
    assert "contract address" in system
    assert "each risk point with its reason" in system
    assert "original information sources" in system
    assert "include the link" in system


def test_system_prompt_no_longer_embeds_address_pattern_guide():
    tool = SimpleNamespace(name="demo_tool", description="Demo tool")

    system = prompt_builder.system_prompt([tool])

    assert "Address Pattern：" not in system
    assert "NEAR can also use a 64-hex implicit account format." not in system


def test_user_prompt_includes_todo_reminder_when_todos_exist():
    prompt = prompt_builder.user_prompt(
        "hello",
        todos=[{"content": "Write tests", "status": "in_progress", "active_form": "Writing tests"}],
    )

    assert "<todo-reminder>" in prompt
    assert "[in_progress] Write tests" in prompt
    assert "active_form: Writing tests" in prompt


def test_agent_initializes_system_prompt_with_loaded_skills(monkeypatch):
    captured = {}
    loaded_skills = [SimpleNamespace(name="brainstorming")]

    class DummyLLM:
        pass

    def fake_system_prompt(tools, skills=None):
        captured["tools"] = tools
        captured["skills"] = skills
        return "SYSTEM"

    monkeypatch.setattr(agent_module, "load_skills", lambda force_reload=True: loaded_skills)
    monkeypatch.setattr(agent_module, "system_prompt", fake_system_prompt)

    agent = agent_module.Agent(llm=DummyLLM(), tools=[])

    assert agent.skills == loaded_skills
    assert captured["skills"] == loaded_skills
    assert agent._system == "SYSTEM"


def test_llm_response_message_strips_think_blocks():
    response = provider.LLMResponse(content="visible<think>hidden</think>done")

    assert response.message["content"] == "visibledone"


def test_openai_completion_response_tracks_cached_and_uncached_tokens():
    usage = SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=45,
        prompt_tokens_details=SimpleNamespace(cached_tokens=20),
        completion_tokens_details=SimpleNamespace(cached_tokens=5),
    )
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="reply", tool_calls=[]))],
        usage=usage,
    )

    response = provider._openai_completion_to_response(completion)

    assert response.prompt_tokens == 120
    assert response.prompt_cache_tokens == 20
    assert response.prompt_uncache_tokens == 100
    assert response.completion_tokens == 45
    assert response.completion_cache_tokens == 5
    assert response.completion_uncache_tokens == 40


def test_default_history_path_uses_new_location_and_migrates_legacy_file(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    legacy = home / ".kittychain_history"
    legacy.write_text("old-entry\n", encoding="utf-8")
    monkeypatch.setattr(cli, "Path", Path)
    monkeypatch.setattr(cli.os.path, "expanduser", lambda value: str(home / value.replace("~/", "")))

    history_path = cli._default_history_path()

    assert history_path == str(home / ".kittychain" / ".history")
    assert Path(history_path).read_text(encoding="utf-8") == "old-entry\n"
    assert not legacy.exists()


def test_repl_tokens_command_uses_new_cached_format(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["/tokens", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(value)

        def print(self, value):
            outputs.append(value)

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def finalize_active_output(self):
            return None

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=11,
            total_prompt_cache_tokens=4,
            total_completion_uncache_tokens=7,
            total_completion_cache_tokens=2,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    cli._repl(fake_agent, fake_config)

    assert any("input=11 (+4 cached" in str(item) for item in outputs)
    assert any("output=7 (+2 cached" in str(item) for item in outputs)


def test_footer_uses_input_output_cached_format(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
        token_provider=lambda: (11, 4, 7, 2),
    )
    reader._footer_width = lambda: 200

    fragments = reader._render_footer_fragments()

    assert "input=11 (+4 cached) output=7 (+2 cached)" in fragments[0][1]


def test_show_help_mentions_copy_mode_and_escape_interrupt():
    outputs = []

    class FakeReader:
        def print(self, value):
            outputs.append(value)

    cli._show_help(io=FakeReader())

    rendered = str(outputs[0].renderable)
    assert "/deep" in rendered
    assert "one message in deep investigation mode" in rendered.lower()
    assert "Ctrl-Y" in rendered
    assert "copy mode" in rendered.lower()
    assert "Esc" in rendered
    assert "interrupt" in rendered.lower()


def test_repl_deep_command_applies_to_one_message_only(monkeypatch):
    seen = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["/deep scan address", "scan again", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            return None

        def print(self, value):
            return None

        def write_raw(self, text, role="assistant", kind="plain"):
            return None

        def finalize_active_output(self):
            return None

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    def fake_run_agent_with_escape_interrupt(agent, user_input, **kwargs):
        seen.append((user_input, getattr(agent, "mode", None)))
        return "done", False, agent

    monkeypatch.setattr(cli, "_run_agent_with_escape_interrupt", fake_run_agent_with_escape_interrupt)

    cli._repl(fake_agent, fake_config)

    assert seen == [("scan address", "deep"), ("scan again", "normal")]


def test_history_copy_mode_transfers_focus_and_returns_to_input(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )

    assert reader.application.layout.current_control == reader.input_area.window.content

    reader._enter_history_copy_mode_ui()

    assert reader._history_copy_mode is True
    assert reader.application.layout.current_control == reader.history_window.content

    reader._exit_history_copy_mode_ui()

    assert reader._history_copy_mode is False
    assert reader.application.layout.current_control == reader.input_area.window.content


def test_exit_history_copy_mode_clears_selection(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )
    reader.history_buffer.set_document(cli.Document("alpha beta gamma"), bypass_readonly=True)
    reader.history_buffer.cursor_position = 0
    reader.history_buffer.start_selection()
    reader.history_buffer.cursor_position = 5

    reader._enter_history_copy_mode_ui()
    assert reader.history_buffer.selection_state is not None

    reader._exit_history_copy_mode_ui()

    assert reader.history_buffer.selection_state is None


def test_input_area_focuses_on_click_to_exit_history_copy_mode(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )

    assert reader.input_area.window.content.focus_on_click()


def test_copy_mode_key_bindings_include_enter_and_exit_shortcuts(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )

    bindings = {
        tuple(key.value for key in binding.keys)
        for binding in reader._build_key_bindings().bindings
    }

    assert ("c-y",) in bindings
    assert ("c-i",) in bindings


def test_footer_shows_copy_mode_hint_when_enabled(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
        token_provider=lambda: (11, 4, 7, 2),
    )
    reader._footer_width = lambda: 200

    reader._enter_history_copy_mode_ui()
    fragments = reader._render_footer_fragments()

    assert "Copy mode" in fragments[0][1]
    assert "Ctrl-Y" in fragments[0][1]


def test_copy_history_selection_sends_text_to_clipboard_and_exits(tmp_path, monkeypatch):
    copied = {}
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )
    reader.history_buffer.set_document(cli.Document("alpha beta gamma"), bypass_readonly=True)
    reader.history_buffer.cursor_position = 0
    reader.history_buffer.start_selection()
    reader.history_buffer.cursor_position = 5
    reader._enter_history_copy_mode_ui()

    monkeypatch.setattr(cli, "_copy_text_to_system_clipboard", lambda text: copied.setdefault("text", text) or True)

    reader._copy_history_selection_to_clipboard_ui()

    assert copied["text"] == "alpha"
    assert reader.application.clipboard.get_data().text == "alpha"
    assert reader._history_copy_mode is False
    assert reader.history_buffer.selection_state is None
    assert reader.application.layout.current_control == reader.input_area.window.content


def test_mouse_selection_in_copy_mode_autocopies_and_returns_to_input(tmp_path, monkeypatch):
    copied = {}
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )
    reader._append_history_item_ui("assistant", "plain", "alpha beta gamma")
    control = reader.history_window.content
    reader._enter_history_copy_mode_ui()
    monkeypatch.setattr(cli, "_copy_text_to_system_clipboard", lambda text: copied.setdefault("text", text) or True)

    control._last_get_processed_line = lambda y: SimpleNamespace(display_to_source=lambda x: x)

    with set_app(reader.application):
        control.mouse_handler(MouseEvent(Point(x=0, y=0), MouseEventType.MOUSE_DOWN, MouseButton.LEFT, frozenset()))
        control.mouse_handler(MouseEvent(Point(x=5, y=0), MouseEventType.MOUSE_MOVE, MouseButton.LEFT, frozenset()))
        control.mouse_handler(MouseEvent(Point(x=5, y=0), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))

    assert copied["text"] == "alpha"
    assert reader.application.clipboard.get_data().text == "alpha"
    assert reader._history_copy_mode is False
    assert reader.application.layout.current_control == reader.input_area.window.content


def test_history_selection_style_uses_explicit_high_contrast_colors():
    attrs = cli._APP_STYLE.get_attrs_for_style_str("class:selected")

    assert attrs.color
    assert attrs.bgcolor


def test_history_style_processor_preserves_selection_for_assistant_markdown():
    metadata = [
        {
            "base_style": "class:history.assistant",
            "markdown": True,
            "markdown_kind": "markdown",
            "raw_text": "hello",
        }
    ]
    processor = cli.HistoryStyleProcessor(lambda: metadata)
    transformed = processor.apply_transformation(
        TransformationInput(
            buffer_control=None,
            document=cli.Document("hello"),
            lineno=0,
            source_to_display=lambda i: i,
            fragments=[("class:selected", "hello")],
            width=80,
            height=1,
        )
    )

    assert any("selected" in style for style, _text, *_rest in transformed.fragments)


def test_tool_role_uses_gray_history_style():
    attrs = cli._APP_STYLE.get_attrs_for_style_str("class:history.tool")

    assert attrs.color == "888888"


def test_render_message_to_text_for_tool_shows_only_tool_body():
    rendered = cli.render_message_to_text("tool", "plain", "Browser summary")

    assert rendered == "Browser summary"


def test_history_renders_tool_result_without_blank_line_before_it(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )

    reader._append_history_item_ui("system", "plain", "Tool call details")
    reader.write_raw("Browser summary", role="tool", kind="plain")
    reader.finalize_active_output()

    assert "Tool call details\nBrowser summary" in reader.history_buffer.text
    assert "Tool call details\n\nBrowser summary" not in reader.history_buffer.text


def test_history_style_does_not_shift_gray_tool_style_onto_following_blank_line(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
    )

    reader._append_history_item_ui("system", "plain", "Tool call details")
    reader.write_raw("Browser summary", role="tool", kind="plain")
    reader.finalize_active_output()
    reader.write_raw("Assistant reply", role="assistant", kind="plain")
    reader.finalize_active_output()

    lines = reader.history_buffer.text.split("\n")
    metadata = reader._history_line_metadata

    assistant_index = lines.index("Assistant reply")
    blank_index = lines.index("")

    assert metadata[blank_index].get("base_style", "") != "class:history.tool"
    assert metadata[assistant_index].get("base_style") == "class:history.assistant"


def test_repl_streams_web_browser_tool_output_only(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["scan address", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(("startup", value))

        def print(self, value):
            outputs.append(("print", value))

        def write_raw(self, text, role="assistant", kind="plain"):
            outputs.append(("write_raw", text, role, kind))

        def write(self, value):
            outputs.append(("write", value))

        def finalize_active_output(self):
            return None

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    def fake_run_agent_with_escape_interrupt(
        agent,
        user_input,
        on_token=None,
        on_tool=None,
        on_tool_output=None,
        **kwargs,
    ):
        on_tool("web_browser", {"url": "https://example.com", "prompt": "scan"})
        on_tool_output("web_browser", "Browser summary")
        on_tool("bash", {"command": "pwd"})
        on_tool_output("bash", "shell output")
        return "", False, agent

    monkeypatch.setattr(cli, "_run_agent_with_escape_interrupt", fake_run_agent_with_escape_interrupt)

    cli._repl(fake_agent, fake_config)

    assert ("write_raw", "Browser summary", "tool", "plain") in outputs
    assert ("write_raw", "shell output", "tool", "plain") not in outputs


def test_repl_streams_ask_user_tool_output(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["scan address", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(("startup", value))

        def print(self, value):
            outputs.append(("print", value))

        def write_raw(self, text, role="assistant", kind="plain"):
            outputs.append(("write_raw", text, role, kind))

        def finalize_active_output(self):
            return None

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    def fake_run_agent_with_escape_interrupt(
        agent,
        user_input,
        on_token=None,
        on_tool=None,
        on_tool_output=None,
        **kwargs,
    ):
        on_tool("ask_user", {"questions": [{"header": "Mode"}]})
        on_tool_output("ask_user", "User answers:\n- Mode: proceed")
        return "done", False, agent

    monkeypatch.setattr(cli, "_run_agent_with_escape_interrupt", fake_run_agent_with_escape_interrupt)

    cli._repl(fake_agent, fake_config)

    assert ("write_raw", "User answers:\n- Mode: proceed", "tool", "plain") in outputs


def test_repl_truncates_web_browser_tool_output_to_first_five_lines(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["scan address", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(("startup", value))

        def print(self, value):
            outputs.append(("print", value))

        def write_raw(self, text, role="assistant", kind="plain"):
            outputs.append(("write_raw", text, role, kind))

        def finalize_active_output(self):
            return None

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    def fake_run_agent_with_escape_interrupt(
        agent,
        user_input,
        on_token=None,
        on_tool=None,
        on_tool_output=None,
        **kwargs,
    ):
        on_tool("web_browser", {"url": "https://example.com", "prompt": "scan"})
        on_tool_output("web_browser", "1\n2\n3\n4\n5\n6\n7")
        return "", False, agent

    monkeypatch.setattr(cli, "_run_agent_with_escape_interrupt", fake_run_agent_with_escape_interrupt)

    cli._repl(fake_agent, fake_config)

    assert ("write_raw", "1\n2\n3\n4\n5", "tool", "plain") in outputs


def test_repl_truncates_write_report_tool_output_to_first_five_lines(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["scan address", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(("startup", value))

        def print(self, value):
            outputs.append(("print", value))

        def write_raw(self, text, role="assistant", kind="plain"):
            outputs.append(("write_raw", text, role, kind))

        def finalize_active_output(self):
            return None

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    def fake_run_agent_with_escape_interrupt(
        agent,
        user_input,
        on_token=None,
        on_tool=None,
        on_tool_output=None,
        **kwargs,
    ):
        on_tool("write_report", {"path": "/tmp/report.html"})
        on_tool_output("write_report", "1\n2\n3\n4\n5\n6\n7")
        return "done", False, agent

    monkeypatch.setattr(cli, "_run_agent_with_escape_interrupt", fake_run_agent_with_escape_interrupt)

    cli._repl(fake_agent, fake_config)

    assert ("write_raw", "1\n2\n3\n4\n5", "tool", "plain") in outputs


def test_repl_streams_todo_write_tool_output_without_showing_tool_call(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["scan address", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(("startup", value))

        def print(self, value):
            outputs.append(("print", value))

        def write_raw(self, text, role="assistant", kind="plain"):
            outputs.append(("write_raw", text, role, kind))

        def write(self, value):
            outputs.append(("write", value))

        def finalize_active_output(self):
            return None

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    def fake_run_agent_with_escape_interrupt(agent, user_input, on_tool=None, on_tool_output=None, **kwargs):
        on_tool("todo_write", {"todos": [{"content": "Task", "status": "pending"}]})
        on_tool_output("todo_write", "Todos updated.\n- [pending] Task")
        return "done", False, agent

    monkeypatch.setattr(cli, "_run_agent_with_escape_interrupt", fake_run_agent_with_escape_interrupt)

    cli._repl(fake_agent, fake_config)

    assert ("write_raw", "Todos updated.\n- [pending] Task", "tool", "plain") in outputs
    assert not any(item[0] == "print" and "Tool Call: todo_write" in str(item[1]) for item in outputs if len(item) >= 2)


def test_repl_streams_brief_tool_output_without_showing_tool_call(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["scan address", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(("startup", value))

        def print(self, value):
            outputs.append(("print", value))

        def write_raw(self, text, role="assistant", kind="plain"):
            outputs.append(("write_raw", text, role, kind))

        def write(self, value):
            outputs.append(("write", value))

        def finalize_active_output(self):
            return None

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace()

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")

    def fake_run_agent_with_escape_interrupt(agent, user_input, on_tool=None, on_tool_output=None, **kwargs):
        on_tool("brief", {"message": "Working on it"})
        on_tool_output("brief", "Sent brief message (normal).\nWorking on it")
        return "done", False, agent

    monkeypatch.setattr(cli, "_run_agent_with_escape_interrupt", fake_run_agent_with_escape_interrupt)

    cli._repl(fake_agent, fake_config)

    assert ("write_raw", "Sent brief message (normal).\nWorking on it", "tool", "plain") in outputs
    assert not any(item[0] == "print" and "Tool Call: brief" in str(item[1]) for item in outputs if len(item) >= 2)


def test_render_tool_call_details_limits_each_argument_to_single_truncated_line():
    panel = cli._render_tool_call_details(
        "write_report",
        {
            "path": "/tmp/report.html",
            "content": "line1\nline2\nline3",
            "graph_data": {"node": [{"address": "0x1", "chain_name": "Ethereum"} for _ in range(3)]},
        },
    )

    rendered = cli._render_to_plain_text(panel, width=100)

    assert "line1 line2 line3..." in rendered
    assert "line1\nline2" not in rendered
    assert "graph_data" in rendered
    assert "..." in rendered


def test_repl_save_command_emits_plain_system_messages_without_rich_markup(monkeypatch):
    outputs = []

    class FakeReader:
        rich_console = None

        def __init__(self):
            self.commands = ["/save", "/quit"]

        def _history_render_width(self):
            return 80

        def print_startup(self, value):
            outputs.append(("startup", value))

        def print(self, value):
            outputs.append(("print", value))

        def run(self, handler, message=None):
            for command in self.commands:
                handler(command)

        def attach_cancel_event(self, _event):
            return None

        def detach_cancel_event(self, _event):
            return None

        def finalize_active_output(self):
            return None

        def request_exit(self):
            return None

    fake_agent = SimpleNamespace(
        skills=[],
        messages=[{"role": "user", "content": "hello"}],
        llm=SimpleNamespace(
            total_prompt_uncache_tokens=0,
            total_prompt_cache_tokens=0,
            total_completion_uncache_tokens=0,
            total_completion_cache_tokens=0,
        ),
    )
    fake_config = SimpleNamespace(model="demo-model")

    monkeypatch.setattr(cli, "_build_input_reader", lambda *args, **kwargs: FakeReader())
    monkeypatch.setattr(cli, "_render_startup_header", lambda config, width=None: "startup")
    monkeypatch.setattr(cli, "save_session", lambda messages, model: "session_123")

    cli._repl(fake_agent, fake_config)

    printed = [value for kind, value in outputs if kind == "print"]
    assert "Session saved: session_123" in printed
    assert "Resume with: kittychain -r session_123" in printed
    assert all("[" not in value and "]" not in value for value in printed)


def test_agent_emits_web_browser_result_to_tool_output_callback():
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def chat(self, messages, tools=None, on_token=None, cancel_event=None):
            self.calls += 1
            if self.calls == 1:
                return provider.LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="tool-1", name="web_browser", arguments={"url": "https://example.com"})],
                )
            return provider.LLMResponse(content="done")

    class FakeTool:
        name = "web_browser"
        description = "Fetches browser content"
        parameters = {}

        def bind_agent(self, agent):
            self.agent = agent

        def schema(self):
            return {
                "type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
            }

        def execute(self, url):
            return "Browser summary"

    agent = agent_module.Agent(llm=FakeLLM(), tools=[FakeTool()])
    seen = []

    response = agent.chat("scan", on_tool_output=lambda name, text: seen.append((name, text)))

    assert response == "done"
    assert seen == [("web_browser", "Browser summary")]


def test_agent_emits_write_report_result_to_tool_output_callback():
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def chat(self, messages, tools=None, on_token=None, cancel_event=None):
            self.calls += 1
            if self.calls == 1:
                return provider.LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="tool-1", name="write_report", arguments={"path": "/tmp/report.html"})],
                )
            return provider.LLMResponse(content="done")

    class FakeTool:
        name = "write_report"
        description = "Writes report files"
        parameters = {}

        def bind_agent(self, agent):
            self.agent = agent

        def schema(self):
            return {
                "type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
            }

        def execute(self, path):
            return "line1\nline2\nline3\nline4\nline5\nline6"

    agent = agent_module.Agent(llm=FakeLLM(), tools=[FakeTool()])
    seen = []

    response = agent.chat("scan", on_tool_output=lambda name, text: seen.append((name, text)))

    assert response == "done"
    assert seen == [("write_report", "line1\nline2\nline3\nline4\nline5\nline6")]


def test_agent_emits_todo_write_result_to_tool_output_callback():
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def chat(self, messages, tools=None, on_token=None, cancel_event=None):
            self.calls += 1
            if self.calls == 1:
                return provider.LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="tool-1", name="todo_write", arguments={"todos": []})],
                )
            return provider.LLMResponse(content="done")

    class FakeTool:
        name = "todo_write"
        description = "Updates todos"
        parameters = {}

        def bind_agent(self, agent):
            self.agent = agent

        def schema(self):
            return {
                "type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
            }

        def execute(self, todos):
            return "Todos updated.\n- [pending] Task"

    agent = agent_module.Agent(llm=FakeLLM(), tools=[FakeTool()])
    seen = []

    response = agent.chat("scan", on_tool_output=lambda name, text: seen.append((name, text)))

    assert response == "done"
    assert seen == [("todo_write", "Todos updated.\n- [pending] Task")]


def test_agent_emits_brief_result_to_tool_output_callback():
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def chat(self, messages, tools=None, on_token=None, cancel_event=None):
            self.calls += 1
            if self.calls == 1:
                return provider.LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="tool-1", name="brief", arguments={"message": "Working on it"})],
                )
            return provider.LLMResponse(content="done")

    class FakeTool:
        name = "brief"
        description = "Sends brief updates"
        parameters = {}

        def bind_agent(self, agent):
            self.agent = agent

        def schema(self):
            return {
                "type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
            }

        def execute(self, message):
            return "Sent brief message (normal).\nWorking on it"

    agent = agent_module.Agent(llm=FakeLLM(), tools=[FakeTool()])
    seen = []

    response = agent.chat("scan", on_tool_output=lambda name, text: seen.append((name, text)))

    assert response == "done"
    assert seen == [("brief", "Sent brief message (normal).\nWorking on it")]
