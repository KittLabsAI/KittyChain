import json
from pathlib import Path

import pytest

from kittychain.config import ApiConfig, Config, StoredModelConfig


def test_config_from_missing_file_uses_defaults(tmp_path: Path):
    config = Config.from_file(tmp_path / "missing.json")

    assert len(config.models) == 1
    assert config.models[0].is_default is True
    assert config.apis == ApiConfig()
    assert config.max_tokens == 32000
    assert config.temperature == 0.0
    assert config.max_context_tokens == 200000


def test_config_round_trip_persists_models_and_apis(tmp_path: Path):
    path = tmp_path / "config.json"
    original = Config(
        interface="openai",
        model="gpt-4.1",
        api_key="model-key",
        base_url="https://example.invalid/v1",
        models=[
            StoredModelConfig(
                interface="openai",
                provider="OpenRouter",
                api_key="model-key",
                model_name="gpt-4.1",
                base_url="https://example.invalid/v1",
            )
        ],
        apis=ApiConfig(kittychain_api_key="kitty-key"),
    )

    original.write(path)
    loaded = Config.from_file(path)

    assert len(loaded.models) == 2
    assert loaded.models[0].provider == "Kitty"
    assert loaded.models[0].is_default is True
    assert loaded.models[1] == original.models[0]
    assert loaded.apis == original.apis
    assert loaded.interface == "openai"
    assert loaded.model == "kitty-2.1"


def test_config_round_trip_persists_only_kittychain_api_key(tmp_path: Path):
    path = tmp_path / "config.json"

    Config(
        apis=ApiConfig(
            kittychain_api_key="kitty-key",
            dune_api_key="dune",
            coingecko_api_key="cg-key",
            okx_api_key="okx-key",
        )
    ).write(path)
    loaded = Config.from_file(path)

    assert loaded.apis.kittychain_api_key == "kitty-key"
    assert loaded.apis.dune_api_key == ""
    assert loaded.apis.coingecko_api_key == ""
    assert loaded.apis.okx_api_key == ""


def test_config_from_old_file_without_apis_uses_empty_api_defaults(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(
        """
{
  "models": [
    {
      "interface": "openai",
      "provider": "OpenRouter",
      "api_key": "abc",
      "model_name": "gpt-4.1",
      "base_url": "https://openrouter.ai/api/v1"
    }
  ]
}
""".strip()
    )

    loaded = Config.from_file(path)

    assert loaded.apis == ApiConfig()


def test_config_invalid_json_raises_value_error(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not-json}")

    with pytest.raises(ValueError):
        Config.from_file(path)


def test_default_model_constants_are_exported():
    from kittychain.config import (
        DEFAULT_MODEL_PROVIDER,
        DEFAULT_MODEL_BASE_URL,
        DEFAULT_MODEL_INTERFACE,
        DEFAULT_MODEL_NAME,
    )

    assert DEFAULT_MODEL_PROVIDER == "Kitty"
    assert DEFAULT_MODEL_BASE_URL == "https://kittyhome.pages.dev/kitty/v1"
    assert DEFAULT_MODEL_INTERFACE == "openai"
    assert DEFAULT_MODEL_NAME == "kitty-2.1"


def test_stored_model_config_has_is_default_flag():
    model = StoredModelConfig(
        interface="openai",
        provider="Kitty",
        api_key="key",
        model_name="kitty-2.1",
        base_url="https://kittyhome.pages.dev/kitty/v1",
        is_default=True,
    )

    assert model.is_default is True

    regular = StoredModelConfig(
        interface="openai",
        provider="OpenRouter",
        api_key="key",
        model_name="gpt-4.1",
        base_url="https://openrouter.ai/api/v1",
    )

    assert regular.is_default is False


def test_config_from_missing_file_injects_default_model(tmp_path: Path):
    config = Config.from_file(tmp_path / "missing.json")

    assert len(config.models) == 1
    default = config.models[0]
    assert default.provider == "Kitty"
    assert default.interface == "openai"
    assert default.model_name == "kitty-2.1"
    assert default.base_url == "https://kittyhome.pages.dev/kitty/v1"
    assert default.is_default is True
    assert default.api_key == ""  # no kittychain_api_key set


def test_config_from_file_prepends_default_model_before_user_models(tmp_path: Path):
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
        apis=ApiConfig(kittychain_api_key="kitty-key"),
    ).write(path)

    loaded = Config.from_file(path)

    assert len(loaded.models) == 2
    assert loaded.models[0].provider == "Kitty"
    assert loaded.models[0].is_default is True
    assert loaded.models[0].api_key == "kitty-key"
    assert loaded.models[1].provider == "OpenRouter"
    assert loaded.models[1].is_default is False


def test_config_default_model_uses_kittychain_api_key(tmp_path: Path):
    path = tmp_path / "config.json"
    Config(
        apis=ApiConfig(kittychain_api_key="my-kitty-key"),
    ).write(path)

    loaded = Config.from_file(path)

    assert loaded.models[0].api_key == "my-kitty-key"
    assert loaded.api_key == "my-kitty-key"


def test_config_to_payload_excludes_default_model(tmp_path: Path):
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
        apis=ApiConfig(kittychain_api_key="kitty-key"),
    ).write(path)

    loaded = Config.from_file(path)
    payload = loaded.to_payload()

    assert len(payload["models"]) == 1
    assert payload["models"][0]["provider"] == "OpenRouter"


def test_config_round_trip_with_default_model(tmp_path: Path):
    path = tmp_path / "config.json"
    Config(
        apis=ApiConfig(kittychain_api_key="kitty-key"),
    ).write(path)

    loaded = Config.from_file(path)
    loaded.write(path)

    raw = json.loads(path.read_text())
    assert raw["models"] == []
