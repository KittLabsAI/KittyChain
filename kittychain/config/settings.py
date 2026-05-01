"""Configuration loaded from ~/.kittychain/config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".kittychain" / "config.json"
API_FIELDS = (
    "kittychain_api_key",
)
LEGACY_API_FIELDS = (
    "dune_api_key",
    "goplus_api_key",
    "goplus_api_secret",
    "alchemy_api_key",
    "chainbase_api_key",
    "coingecko_api_key",
    "okx_api_key",
    "okx_secret_key",
    "okx_passphrase",
)

DEFAULT_MODEL_PROVIDER = "Kitty"
DEFAULT_MODEL_BASE_URL = "https://kittyhome.pages.dev/kitty/v1"
DEFAULT_MODEL_INTERFACE = "openai"
DEFAULT_MODEL_NAME = "kitty-2.1"


def _normalize_interface(value: object, *, field_name: str) -> str:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    interface = str(value).strip().lower()
    if not interface:
        raise ValueError(f"{field_name} is required")
    if interface not in {"openai", "anthropic"}:
        raise ValueError(f"{field_name} must be 'openai' or 'anthropic'")
    return interface


def _normalize_provider(value: object, *, field_name: str) -> str:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    provider = str(value).strip()
    if not provider:
        raise ValueError(f"{field_name} is required")
    return provider


def _require_text(data: dict, key: str, *, field_name: str) -> str:
    value = data.get(key)
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return str(value)


@dataclass(frozen=True)
class StoredModelConfig:
    interface: str
    provider: str
    api_key: str
    model_name: str
    base_url: str | None = None
    is_default: bool = False


@dataclass(frozen=True)
class ApiConfig:
    kittychain_api_key: str = ""
    dune_api_key: str = ""
    goplus_api_key: str = ""
    goplus_api_secret: str = ""
    alchemy_api_key: str = ""
    chainbase_api_key: str = ""
    coingecko_api_key: str = ""
    okx_api_key: str = ""
    okx_secret_key: str = ""
    okx_passphrase: str = ""

    @classmethod
    def from_dict(cls, raw: object) -> "ApiConfig":
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ValueError("apis must be an object")
        payload = {}
        for field_name in (*API_FIELDS, *LEGACY_API_FIELDS):
            value = raw.get(field_name, "")
            payload[field_name] = "" if value in (None, "") else str(value)
        return cls(**payload)

    def to_dict(self) -> dict[str, str]:
        return {field_name: getattr(self, field_name) for field_name in API_FIELDS}


@dataclass
class Config:
    interface: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 32_000
    temperature: float = 0.0
    max_context_tokens: int = 200_000
    models: list[StoredModelConfig] = field(default_factory=list)
    apis: ApiConfig = field(default_factory=ApiConfig)

    def to_payload(self) -> dict:
        active_index = self.active_model_index()
        ordered_models = list(self.models)
        if active_index is not None:
            ordered_models = [
                ordered_models[active_index],
                *ordered_models[:active_index],
                *ordered_models[active_index + 1 :],
            ]

        return {
            "models": [
                {
                    "interface": model.interface,
                    "provider": model.provider,
                    "api_key": model.api_key,
                    "model_name": model.model_name,
                    "base_url": model.base_url,
                }
                for model in ordered_models
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "max_context": self.max_context_tokens,
            "apis": self.apis.to_dict(),
        }

    def write(self, config_path: Path | str | None = None) -> None:
        path = Path(config_path).expanduser() if config_path is not None else CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_payload(), indent=2) + "\n")

    def active_model_index(self) -> int | None:
        for index, model in enumerate(self.models):
            if (
                model.interface == self.interface
                and model.model_name == self.model
                and model.api_key == self.api_key
                and model.base_url == self.base_url
            ):
                return index
        return None

    def activate_model(self, index: int) -> StoredModelConfig:
        if index < 0 or index >= len(self.models):
            raise ValueError(f"Invalid model index: {index}")

        selected = self.models[index]
        self.interface = selected.interface
        self.model = selected.model_name
        self.api_key = selected.api_key
        self.base_url = selected.base_url
        return selected

    @classmethod
    def from_file(cls, config_path: Path | str | None = None) -> "Config":
        path = Path(config_path).expanduser() if config_path is not None else CONFIG_PATH

        if not path.exists():
            return cls()

        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"{path} must contain a JSON object")

        models = cls._normalize_models(raw)
        active_model = models[0] if models else None

        return cls(
            interface=active_model.interface if active_model is not None else "openai",
            model=active_model.model_name if active_model is not None else "gpt-4o",
            api_key=active_model.api_key if active_model is not None else "",
            base_url=active_model.base_url if active_model is not None else None,
            max_tokens=int(raw.get("max_tokens", 32000)),
            temperature=float(raw.get("temperature", 0.0)),
            max_context_tokens=int(raw.get("max_context", raw.get("max_context_tokens", 200000))),
            models=models,
            apis=ApiConfig.from_dict(raw.get("apis")),
        )

    @staticmethod
    def _normalize_models(raw: dict) -> list[StoredModelConfig]:
        models = raw.get("models")
        if models is None:
            return []
        if not isinstance(models, list):
            raise ValueError("models must be a list")
        return [Config._normalize_model_entry(entry, index) for index, entry in enumerate(models)]

    @staticmethod
    def _normalize_model_entry(entry: object, index: int) -> StoredModelConfig:
        if not isinstance(entry, dict):
            raise ValueError(f"models[{index}] must be an object")

        field_prefix = f"models[{index}]"
        interface = _normalize_interface(entry.get("interface"), field_name=f"{field_prefix}.interface")
        provider = _normalize_provider(entry.get("provider"), field_name=f"{field_prefix}.provider")
        api_key = _require_text(entry, "api_key", field_name=f"{field_prefix}.api_key")
        model_name = _require_text(entry, "model_name", field_name=f"{field_prefix}.model_name")
        base_url = entry.get("base_url")
        if base_url in ("", None):
            base_url = None
        elif not isinstance(base_url, str):
            raise ValueError(f"{field_prefix}.base_url must be a string")

        return StoredModelConfig(
            interface=interface,
            provider=provider,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
        )
