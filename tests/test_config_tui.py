from pathlib import Path

from prompt_toolkit.keys import Keys
from prompt_toolkit.widgets import Dialog as PromptDialog

from kittychain.config.settings import ApiConfig, Config, StoredModelConfig
from kittychain.config.tui import (
    _apply_post_action,
    _build_main_screen_text,
    _edit_apis,
    _move_focus_down,
    load_config_tui_state,
    mask_secret,
    render_api_summary,
    render_model_list,
    run_config_tui,
    write_config_tui_state,
)


def test_mask_secret_hides_middle_characters():
    assert mask_secret("") == "(empty)"
    assert mask_secret("abcd") == "abcd"
    assert mask_secret("abcdefgh") == "abcd...efgh"


def test_load_config_tui_state_reads_model_and_api_sections(tmp_path: Path):
    path = tmp_path / "config.json"
    Config(
        interface="openai",
        model="gpt-4.1",
        api_key="model-key",
        models=[
            StoredModelConfig(
                interface="openai",
                provider="OpenRouter",
                api_key="model-key",
                model_name="gpt-4.1",
                base_url="https://openrouter.ai/api/v1",
            )
        ],
        apis=ApiConfig(kittychain_api_key="kitty-key", dune_api_key="dune", chainbase_api_key="chainbase"),
    ).write(path)

    state = load_config_tui_state(path)

    assert len(state.models) == 2
    assert state.models[0].is_default is True
    assert state.models[1].provider == "OpenRouter"
    assert state.apis.kittychain_api_key == "kitty-key"


def test_write_config_tui_state_persists_only_kittychain_api_key(tmp_path: Path):
    path = tmp_path / "config.json"
    state = load_config_tui_state(path)
    state.apis = ApiConfig(
        kittychain_api_key="kitty-key",
        dune_api_key="dune",
        goplus_api_secret="secret",
        alchemy_api_key="alchemy",
        coingecko_api_key="cg-key",
    )

    write_config_tui_state(state, path)
    loaded = Config.from_file(path)

    assert loaded.apis.kittychain_api_key == "kitty-key"
    assert loaded.apis.dune_api_key == ""
    assert loaded.apis.alchemy_api_key == ""
    assert loaded.apis.coingecko_api_key == ""


def test_apply_post_action_updates_api_state_without_running_dialog_in_event_loop(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    updated = ApiConfig(kittychain_api_key="kitty-key")

    _apply_post_action(
        state,
        "edit_api_key",
        edit_apis=lambda existing: updated,
    )

    assert state.apis == updated


def test_render_api_summary_only_includes_kittychain_api_key():
    summary = render_api_summary(
        ApiConfig(
            kittychain_api_key="kitty-key",
            dune_api_key="dune",
            coingecko_api_key="cg-key",
            okx_api_key="okx-key",
        )
    )

    assert "KITTYCHAIN_API_KEY: kitt...-key" in summary
    assert "Dune API Key" not in summary
    assert "CoinGecko API Key" not in summary
    assert "OKX API Key" not in summary


def test_edit_apis_collects_only_kittychain_api_key():
    prompts = []

    def fake_prompt(title: str, label: str, default: str):
        prompts.append((title, label, default))
        return "kitty-key"

    updated = _edit_apis(ApiConfig(kittychain_api_key="old-key"), prompt_text=fake_prompt)

    assert prompts == [("API Config", "KITTYCHAIN_API_KEY", "old-key")]
    assert updated == ApiConfig(kittychain_api_key="kitty-key")


def test_main_screen_shows_all_config_sections_on_one_page(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    state.models.append(
        type("Model", (), {
            "provider": "OpenRouter",
            "interface": "openai",
            "api_key": "key",
            "model_name": "gpt-4.1",
            "base_url": "https://openrouter.ai/api/v1",
            "is_default": False,
        })()
    )
    state.apis = ApiConfig(kittychain_api_key="kitty-key", dune_api_key="dune")

    screen = _build_main_screen_text(state)

    assert "Models" in screen
    assert "[Add]" in screen
    assert "[Delete]" in screen
    assert "max_tokens: 32000" in screen
    assert "temperature: 0.0" in screen
    assert "max_context: 200000" in screen
    assert "KITTYCHAIN_API_KEY: kitt...-key" in screen
    assert "[Save]" in screen
    assert "[Cancel]" in screen
    assert "e: edit" in screen
    assert "Tab: move" not in screen
    assert "a: add" not in screen
    assert "d: delete" not in screen
    assert "Dune API Key" not in screen
    assert "APIs" not in screen


def test_down_from_last_model_moves_focus_to_add_button(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    state.models = [
        type("Model", (), {
            "provider": "OpenRouter",
            "interface": "openai",
            "api_key": "one",
            "model_name": "gpt-4.1",
            "base_url": "https://openrouter.ai/api/v1",
        })(),
        type("Model", (), {
            "provider": "OpenAI",
            "interface": "openai",
            "api_key": "two",
            "model_name": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
        })(),
    ]

    _move_focus_down(state)
    assert state.focus_section == "models"
    assert state.selected_model_index == 1

    _move_focus_down(state)
    assert state.focus_section == "add_model"
    assert state.selected_model_index == 1


def test_run_config_tui_uses_dialog_style_for_initial_screen(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_dialog(*, title, body, buttons, with_background):
        captured["title"] = title
        captured["buttons"] = [button.text for button in buttons]
        captured["with_background"] = with_background
        captured["body_control"] = body.children[0].content
        captured["body_focusable"] = bool(captured["body_control"].focusable())
        captured["binding_keys"] = {binding.keys for binding in captured["body_control"].key_bindings.bindings}
        return PromptDialog(title=title, body=body, buttons=buttons, with_background=with_background)

    class FakeApplication:
        def __init__(self, *, layout, **kwargs):
            captured["layout"] = layout
            captured["full_screen"] = kwargs["full_screen"]
            captured["focused_control"] = layout.current_control

        def run(self):
            return None

    monkeypatch.setattr("kittychain.config.tui.Dialog", fake_dialog)
    monkeypatch.setattr("kittychain.config.tui.Application", FakeApplication)

    run_config_tui(tmp_path / "config.json")

    assert captured["title"] == "KittyChain Config"
    assert captured["buttons"] == []
    assert captured["with_background"] is True
    assert captured["body_focusable"] is True
    assert captured["focused_control"] is captured["body_control"]
    assert captured["full_screen"] is True
    assert (Keys.Tab,) in captured["binding_keys"]
    assert (Keys.BackTab,) in captured["binding_keys"]
    assert ("e",) in captured["binding_keys"]
    assert ("a",) not in captured["binding_keys"]
    assert ("d",) not in captured["binding_keys"]


def test_apply_post_action_activates_selected_model_without_editing(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    state.models = [
        type("Model", (), {
            "provider": "OpenRouter",
            "interface": "openai",
            "api_key": "one",
            "model_name": "gpt-4.1",
            "base_url": "https://openrouter.ai/api/v1",
        })(),
        type("Model", (), {
            "provider": "OpenAI",
            "interface": "openai",
            "api_key": "two",
            "model_name": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
        })(),
    ]
    state.selected_model_index = 1

    changed = _apply_post_action(
        state,
        "activate_model",
        edit_model=lambda existing=None: (_ for _ in ()).throw(AssertionError("edit should not run")),
    )

    assert changed is True
    assert [model.model_name for model in state.models] == ["gpt-4o", "gpt-4.1"]
    assert state.selected_model_index == 0


def test_apply_post_action_deletes_selected_model(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    state.models = [
        type("Model", (), {
            "provider": "OpenRouter",
            "interface": "openai",
            "api_key": "one",
            "model_name": "gpt-4.1",
            "base_url": "https://openrouter.ai/api/v1",
            "is_default": False,
        })(),
        type("Model", (), {
            "provider": "OpenAI",
            "interface": "openai",
            "api_key": "two",
            "model_name": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "is_default": False,
        })(),
    ]

    changed = _apply_post_action(
        state,
        "delete_model",
        select_model_index=lambda models: 0,
    )

    assert changed is True
    assert [model.model_name for model in state.models] == ["gpt-4o"]


def test_apply_post_action_adds_model_outside_main_application_loop(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    model = type("Model", (), {
        "provider": "OpenRouter",
        "interface": "openai",
        "api_key": "key",
        "model_name": "gpt-4.1",
        "base_url": "https://openrouter.ai/api/v1",
    })()

    _apply_post_action(
        state,
        "add_model",
        edit_model=lambda existing=None: model,
    )

    assert len(state.models) == 1
    assert state.models[0].model_name == "gpt-4.1"


def test_load_config_tui_state_marks_default_model(tmp_path: Path):
    path = tmp_path / "config.json"
    Config(
        apis=ApiConfig(kittychain_api_key="kitty-key"),
    ).write(path)

    state = load_config_tui_state(path)

    assert len(state.models) == 1
    assert state.models[0].is_default is True
    assert state.models[0].provider == "Kitty"


def test_render_model_list_shows_default_label():
    models = [
        type("Model", (), {
            "provider": "Kitty",
            "interface": "openai",
            "api_key": "key",
            "model_name": "kitty-2.1",
            "base_url": "https://kittyhome.pages.dev/kitty/v1",
            "is_default": True,
        })(),
        type("Model", (), {
            "provider": "OpenRouter",
            "interface": "openai",
            "api_key": "key",
            "model_name": "gpt-4.1",
            "base_url": "https://openrouter.ai/api/v1",
            "is_default": False,
        })(),
    ]

    rendered = render_model_list(models)

    assert "Kitty (default)" in rendered
    assert "OpenRouter" in rendered
    assert "OpenRouter (default)" not in rendered


def test_apply_post_action_blocks_edit_on_default_model(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    state.models = [
        type("Model", (), {
            "provider": "Kitty",
            "interface": "openai",
            "api_key": "key",
            "model_name": "kitty-2.1",
            "base_url": "https://kittyhome.pages.dev/kitty/v1",
            "is_default": True,
        })(),
    ]
    state.selected_model_index = 0

    edit_called = False

    def fake_edit(existing=None):
        nonlocal edit_called
        edit_called = True
        return existing

    changed = _apply_post_action(state, "edit_model", edit_model=fake_edit)

    assert changed is False
    assert edit_called is False


def test_apply_post_action_blocks_delete_on_default_model(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    state.models = [
        type("Model", (), {
            "provider": "Kitty",
            "interface": "openai",
            "api_key": "key",
            "model_name": "kitty-2.1",
            "base_url": "https://kittyhome.pages.dev/kitty/v1",
            "is_default": True,
        })(),
    ]

    changed = _apply_post_action(
        state,
        "delete_model",
        select_model_index=lambda models, **kw: 0,
    )

    assert changed is False
    assert len(state.models) == 1


def test_main_screen_shows_default_hint_when_only_default(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    state.models = [
        type("Model", (), {
            "provider": "Kitty",
            "interface": "openai",
            "api_key": "key",
            "model_name": "kitty-2.1",
            "base_url": "https://kittyhome.pages.dev/kitty/v1",
            "is_default": True,
        })(),
    ]

    screen = _build_main_screen_text(state)

    assert "Kitty (default)" in screen
