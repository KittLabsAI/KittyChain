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
DEFAULT_MODEL_SENTINEL = "DEFAULT_MODEL"


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

    def _serialize_model(self, model: StoredModelConfig) -> dict | str:
        if model.is_default:
            return DEFAULT_MODEL_SENTINEL
        return {
            "interface": model.interface,
            "provider": model.provider,
            "api_key": model.api_key,
            "model_name": model.model_name,
            "base_url": model.base_url,
        }

    def to_payload(self) -> dict:
        active_index = self.active_model_index()
        if active_index is not None and active_index > 0:
            ordered = [self.models[active_index], *(
                m for i, m in enumerate(self.models) if i != active_index
            )]
        else:
            ordered = list(self.models)

        payload: dict = {
            "interface": self.interface,
            "model": self.model,
            "api_key": self.api_key,
            "models": [self._serialize_model(m) for m in ordered],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "max_context": self.max_context_tokens,
            "apis": self.apis.to_dict(),
        }
        if self.base_url is not None:
            payload["base_url"] = self.base_url
        return payload

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
        # Move selected model to front (position = active)
        self.models.insert(0, self.models.pop(index))
        self.interface = selected.interface
        self.model = selected.model_name
        self.api_key = selected.api_key
        self.base_url = selected.base_url
        return selected

    @classmethod
    def from_file(cls, config_path: Path | str | None = None) -> "Config":
        path = Path(config_path).expanduser() if config_path is not None else CONFIG_PATH

        if not path.exists():
            apis = ApiConfig()
            default_model = cls._make_default_model(apis.kittychain_api_key)
            return cls(
                interface=default_model.interface,
                model=default_model.model_name,
                api_key=default_model.api_key,
                base_url=default_model.base_url,
                models=[default_model],
                apis=apis,
            )

        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"{path} must contain a JSON object")

        apis = ApiConfig.from_dict(raw.get("apis"))
        models = cls._normalize_models(raw, apis)

        # Ensure default model is always present
        has_default = any(m.is_default for m in models)
        if not has_default:
            # Insert after user's models so user's active (first) stays first
            models.append(cls._make_default_model(apis.kittychain_api_key))

        # Active model: first in list (position-based)
        active = models[0]

        # Backward compat: legacy top-level fields can override active model
        saved_interface = raw.get("interface", "")
        saved_model_name = raw.get("model", "")
        if saved_interface and saved_model_name:
            saved_api_key = raw.get("api_key", "")
            saved_base_url = raw.get("base_url")
            for m in models:
                if (
                    m.interface == saved_interface
                    and m.model_name == saved_model_name
                    and m.api_key == saved_api_key
                    and m.base_url == saved_base_url
                ):
                    active = m
                    # Move matched model to front
                    models.remove(m)
                    models.insert(0, m)
                    break

        return cls(
            interface=active.interface,
            model=active.model_name,
            api_key=active.api_key,
            base_url=active.base_url,
            max_tokens=int(raw.get("max_tokens", 32000)),
            temperature=float(raw.get("temperature", 0.0)),
            max_context_tokens=int(raw.get("max_context", raw.get("max_context_tokens", 200000))),
            models=models,
            apis=apis,
        )

    @staticmethod
    def _normalize_models(raw: dict, apis: ApiConfig | None = None) -> list[StoredModelConfig]:
        models_raw = raw.get("models")
        if models_raw is None:
            return []
        if not isinstance(models_raw, list):
            raise ValueError("models must be a list")
        models = [Config._normalize_model_entry(entry, index) for index, entry in enumerate(models_raw)]
        # Resolve DEFAULT_MODEL sentinel: set api_key from kittychain_api_key
        kitty_key = apis.kittychain_api_key if apis is not None else ""
        models = [
            Config._make_default_model(kitty_key) if m.is_default and m.api_key == "" else m
            for m in models
        ]
        return models

    @staticmethod
    def _make_default_model(api_key: str = "") -> StoredModelConfig:
        return StoredModelConfig(
            interface=DEFAULT_MODEL_INTERFACE,
            provider=DEFAULT_MODEL_PROVIDER,
            api_key=api_key,
            model_name=DEFAULT_MODEL_NAME,
            base_url=DEFAULT_MODEL_BASE_URL,
            is_default=True,
        )

    @staticmethod
    def _normalize_model_entry(entry: object, index: int) -> StoredModelConfig:
        if isinstance(entry, str) and entry == DEFAULT_MODEL_SENTINEL:
            return Config._make_default_model()
        if not isinstance(entry, dict):
            raise ValueError(f"models[{index}] must be an object or '{DEFAULT_MODEL_SENTINEL}'")

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
