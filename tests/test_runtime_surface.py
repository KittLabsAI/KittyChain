from pathlib import Path
from types import SimpleNamespace

import kittychain.cli as cli
import kittychain.llm.provider as provider
import kittychain.prompt.builder as prompt_builder
import kittychain.runtime.agent as agent_module
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

    assert any("input=[cyan]11[/cyan] (+[cyan]4[/cyan] cached" in str(item) for item in outputs)
    assert any("output=[cyan]7[/cyan] (+[cyan]2[/cyan] cached" in str(item) for item in outputs)


def test_footer_uses_input_output_cached_format(tmp_path):
    reader = cli._ReadlineInput(
        str(tmp_path / "history"),
        lambda: [],
        token_provider=lambda: (11, 4, 7, 2),
    )
    reader._footer_width = lambda: 200

    fragments = reader._render_footer_fragments()

    assert "input=11 (+4 cached) output=7 (+2 cached)" in fragments[0][1]
