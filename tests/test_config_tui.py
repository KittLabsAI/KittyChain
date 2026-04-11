from pathlib import Path

from kittychain.config.settings import ApiConfig, Config, StoredModelConfig
from kittychain.config.tui import _apply_post_action, load_config_tui_state, mask_secret, write_config_tui_state


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
        apis=ApiConfig(dune_api_key="dune", chainbase_api_key="chainbase"),
    ).write(path)

    state = load_config_tui_state(path)

    assert len(state.models) == 1
    assert state.apis.dune_api_key == "dune"
    assert state.apis.chainbase_api_key == "chainbase"


def test_write_config_tui_state_persists_api_values(tmp_path: Path):
    path = tmp_path / "config.json"
    state = load_config_tui_state(path)
    state.apis = ApiConfig(
        dune_api_key=state.apis.dune_api_key,
        goplus_api_key=state.apis.goplus_api_key,
        goplus_api_secret="secret",
        alchemy_api_key="alchemy",
        chainbase_api_key=state.apis.chainbase_api_key,
    )

    write_config_tui_state(state, path)
    loaded = Config.from_file(path)

    assert loaded.apis.alchemy_api_key == "alchemy"
    assert loaded.apis.goplus_api_secret == "secret"


def test_apply_post_action_updates_api_state_without_running_dialog_in_event_loop(tmp_path: Path):
    state = load_config_tui_state(tmp_path / "config.json")
    updated = ApiConfig(dune_api_key="dune", chainbase_api_key="chainbase")

    _apply_post_action(
        state,
        "edit_apis",
        edit_apis=lambda existing: updated,
    )

    assert state.apis == updated


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
