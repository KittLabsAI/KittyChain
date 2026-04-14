from pathlib import Path

import pytest

from kittychain.config import ApiConfig, Config, StoredModelConfig


def test_config_from_missing_file_uses_defaults(tmp_path: Path):
    config = Config.from_file(tmp_path / "missing.json")

    assert config.models == []
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
        apis=ApiConfig(
            dune_api_key="dune",
            goplus_api_key="goplus-key",
            goplus_api_secret="goplus-secret",
            alchemy_api_key="alchemy",
            chainbase_api_key="chainbase",
            coingecko_api_key="cg-key",
        ),
    )

    original.write(path)
    loaded = Config.from_file(path)

    assert loaded.models == original.models
    assert loaded.apis == original.apis
    assert loaded.interface == "openai"
    assert loaded.model == "gpt-4.1"


def test_config_round_trip_includes_coingecko_api_key(tmp_path: Path):
    path = tmp_path / "config.json"

    Config(apis=ApiConfig(coingecko_api_key="cg-key")).write(path)
    loaded = Config.from_file(path)

    assert loaded.apis.coingecko_api_key == "cg-key"


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
