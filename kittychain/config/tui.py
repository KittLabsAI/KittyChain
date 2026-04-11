"""Standalone TUI for editing KittyChain model and API configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.shortcuts import button_dialog, input_dialog, message_dialog, radiolist_dialog
from prompt_toolkit.styles import Style

from .presets import PROVIDER_PRESETS, get_provider_preset
from .settings import CONFIG_PATH, ApiConfig, Config, StoredModelConfig

_DEFAULT_MAX_TOKENS = 32_000
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_MAX_CONTEXT = 200_000
_APP_STYLE = Style.from_dict(
    {
        "frame": "fg:#d68786",
        "title.active": "fg:#d68786 bold",
        "title.inactive": "fg:#6b7280",
        "body": "",
        "hint": "fg:#6b7280",
        "error": "fg:#ff5f5f",
    }
)


@dataclass
class ConfigTUIModel:
    provider: str
    interface: str
    api_key: str
    model_name: str
    base_url: str


@dataclass
class ConfigTUIState:
    models: list[ConfigTUIModel] = field(default_factory=list)
    apis: ApiConfig = field(default_factory=ApiConfig)
    issue: str | None = None
    max_tokens: int = _DEFAULT_MAX_TOKENS
    temperature: float = _DEFAULT_TEMPERATURE
    max_context: int = _DEFAULT_MAX_CONTEXT
    focus_section: str = "models"


def _load_raw_defaults(config_path: Path) -> tuple[int, float, int]:
    if not config_path.exists():
        return (_DEFAULT_MAX_TOKENS, _DEFAULT_TEMPERATURE, _DEFAULT_MAX_CONTEXT)

    try:
        raw = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError):
        return (_DEFAULT_MAX_TOKENS, _DEFAULT_TEMPERATURE, _DEFAULT_MAX_CONTEXT)

    if not isinstance(raw, dict):
        return (_DEFAULT_MAX_TOKENS, _DEFAULT_TEMPERATURE, _DEFAULT_MAX_CONTEXT)

    return (
        int(raw.get("max_tokens", _DEFAULT_MAX_TOKENS)),
        float(raw.get("temperature", _DEFAULT_TEMPERATURE)),
        int(raw.get("max_context", raw.get("max_context_tokens", _DEFAULT_MAX_CONTEXT))),
    )


def load_config_tui_state(config_path: Path | str | None = None) -> ConfigTUIState:
    path = Path(config_path).expanduser() if config_path is not None else CONFIG_PATH
    max_tokens, temperature, max_context = _load_raw_defaults(path)

    if not path.exists():
        return ConfigTUIState(
            issue=f"Config file not found: {path}\nUse this screen to create one.",
            max_tokens=max_tokens,
            temperature=temperature,
            max_context=max_context,
        )

    try:
        config = Config.from_file(path)
    except ValueError as exc:
        return ConfigTUIState(
            issue=f"Config needs repair:\n{exc}",
            max_tokens=max_tokens,
            temperature=temperature,
            max_context=max_context,
        )

    return ConfigTUIState(
        models=[
            ConfigTUIModel(
                provider=model.provider,
                interface=model.interface,
                api_key=model.api_key,
                model_name=model.model_name,
                base_url=model.base_url or "",
            )
            for model in config.models
        ],
        apis=config.apis,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        max_context=config.max_context_tokens,
    )


def build_model_from_provider(
    provider: str,
    *,
    api_key: str = "",
    model_name: str = "",
    base_url: str | None = None,
) -> ConfigTUIModel:
    preset = get_provider_preset(provider)
    interface = preset.interface if preset is not None else "openai"
    resolved_base_url = base_url if base_url is not None else (preset.base_url if preset is not None else "")
    return ConfigTUIModel(
        provider=provider,
        interface=interface,
        api_key=api_key,
        model_name=model_name,
        base_url=resolved_base_url,
    )


def render_model_list(models: list[ConfigTUIModel]) -> str:
    provider_width = max(len("Provider"), *(len(model.provider) for model in models)) if models else len("Provider")
    model_width = max(len("Model"), *(len(model.model_name) for model in models)) if models else len("Model")
    base_width = max(len("Base URL"), *(len(model.base_url) for model in models)) if models else len("Base URL")

    header = f"{'Provider':<{provider_width}} | {'Model':<{model_width}} | {'Base URL':<{base_width}}"
    divider = f"{'-' * provider_width}-+-{'-' * model_width}-+-{'-' * base_width}"
    if not models:
        return "\n".join([header, divider, "(no models configured yet)"])

    rows = [
        f"{model.provider:<{provider_width}} | {model.model_name:<{model_width}} | {model.base_url:<{base_width}}"
        for model in models
    ]
    return "\n".join([header, divider, *rows])


def mask_secret(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 4:
        return value
    return f"{value[:4]}...{value[-4:]}"


def render_api_summary(apis: ApiConfig) -> str:
    return "\n".join(
        [
            f"Dune API Key: {mask_secret(apis.dune_api_key)}",
            f"GoPlus API Key: {mask_secret(apis.goplus_api_key)}",
            f"GoPlus API Secret: {mask_secret(apis.goplus_api_secret)}",
            f"Alchemy API Key: {mask_secret(apis.alchemy_api_key)}",
            f"Chainbase API Key: {mask_secret(apis.chainbase_api_key)}",
        ]
    )


def write_config_tui_state(state: ConfigTUIState, config_path: Path | str | None = None) -> None:
    path = Path(config_path).expanduser() if config_path is not None else CONFIG_PATH
    active_model = state.models[0] if state.models else None
    config = Config(
        interface=active_model.interface if active_model is not None else "openai",
        model=active_model.model_name if active_model is not None else "gpt-4o",
        api_key=active_model.api_key if active_model is not None else "",
        base_url=active_model.base_url if active_model is not None else None,
        max_tokens=state.max_tokens,
        temperature=state.temperature,
        max_context_tokens=state.max_context,
        models=[
            StoredModelConfig(
                interface=model.interface,
                provider=model.provider,
                api_key=model.api_key,
                model_name=model.model_name,
                base_url=model.base_url or None,
            )
            for model in state.models
        ],
        apis=state.apis,
    )
    config.write(path)


def _select_provider(current_provider: str | None = None) -> str | None:
    values = [(preset.provider, preset.provider) for preset in PROVIDER_PRESETS]
    return radiolist_dialog(
        title="Select Provider",
        text="Choose a provider preset for this model.",
        values=values,
        default=current_provider or values[0][0],
    ).run()


def _prompt_text(title: str, label: str, default: str = "") -> str | None:
    return input_dialog(
        title=title,
        text=label,
        default=default,
    ).run()


def _edit_model(existing: ConfigTUIModel | None = None) -> ConfigTUIModel | None:
    selected_provider = _select_provider(existing.provider if existing is not None else None)
    if selected_provider is None:
        return None

    preset = get_provider_preset(selected_provider)
    api_key = _prompt_text("Model Config", "API Key", existing.api_key if existing is not None else "")
    if api_key is None:
        return None
    model_name = _prompt_text("Model Config", "Model Name", existing.model_name if existing is not None else "")
    if model_name is None:
        return None
    default_base_url = (
        existing.base_url
        if existing is not None and existing.provider == selected_provider
        else (preset.base_url if preset is not None else (existing.base_url if existing is not None else ""))
    )
    base_url = _prompt_text("Model Config", "Base URL", default_base_url)
    if base_url is None:
        return None

    return build_model_from_provider(
        selected_provider,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
    )


def _select_model_index(models: list[ConfigTUIModel]) -> int | None:
    if not models:
        message_dialog(
            title="Edit Model",
            text="No configured models yet. Add one first.",
        ).run()
        return None

    values = [
        (index, f"{model.provider} | {model.model_name} | {model.base_url}")
        for index, model in enumerate(models)
    ]
    return radiolist_dialog(
        title="Edit Model",
        text="Choose an existing model to edit.",
        values=values,
        default=values[0][0],
    ).run()


def _edit_apis(existing: ApiConfig) -> ApiConfig | None:
    dune_api_key = _prompt_text("API Config", "Dune API Key", existing.dune_api_key)
    if dune_api_key is None:
        return None
    goplus_api_key = _prompt_text("API Config", "GoPlus API Key", existing.goplus_api_key)
    if goplus_api_key is None:
        return None
    goplus_api_secret = _prompt_text("API Config", "GoPlus API Secret", existing.goplus_api_secret)
    if goplus_api_secret is None:
        return None
    alchemy_api_key = _prompt_text("API Config", "Alchemy API Key", existing.alchemy_api_key)
    if alchemy_api_key is None:
        return None
    chainbase_api_key = _prompt_text("API Config", "Chainbase API Key", existing.chainbase_api_key)
    if chainbase_api_key is None:
        return None
    return ApiConfig(
        dune_api_key=dune_api_key,
        goplus_api_key=goplus_api_key,
        goplus_api_secret=goplus_api_secret,
        alchemy_api_key=alchemy_api_key,
        chainbase_api_key=chainbase_api_key,
    )


def _build_main_screen_text(state: ConfigTUIState) -> str:
    lines: list[str] = []
    if state.issue:
        lines.extend([state.issue, ""])
    model_title = ">> Models" if state.focus_section == "models" else "   Models"
    api_title = ">> APIs" if state.focus_section == "apis" else "   APIs"
    lines.extend(
        [
            model_title,
            render_model_list(state.models),
            "",
            api_title,
            render_api_summary(state.apis),
            "",
            "Tab: switch section | Enter: edit active section | a: add model | e: edit | Ctrl-S: save | q: quit",
        ]
    )
    return "\n".join(lines)


def _apply_post_action(
    state: ConfigTUIState,
    action: str,
    *,
    edit_model=_edit_model,
    edit_apis=_edit_apis,
    select_model_index=_select_model_index,
) -> bool:
    if action == "add_model":
        updated = edit_model()
        if updated is None:
            return False
        state.models.append(updated)
        state.issue = None
        return True

    if action == "edit_models":
        if state.models:
            index = select_model_index(state.models)
            if index is None:
                return False
            updated = edit_model(state.models[index])
            if updated is None:
                return False
            state.models[index] = updated
            state.issue = None
            return True

        updated = edit_model()
        if updated is None:
            return False
        state.models.append(updated)
        state.issue = None
        return True

    if action == "edit_apis":
        updated = edit_apis(state.apis)
        if updated is None:
            return False
        state.apis = updated
        state.issue = None
        return True

    return False


def run_config_tui(config_path: Path | str | None = None) -> int:
    path = Path(config_path).expanduser() if config_path is not None else CONFIG_PATH
    state = load_config_tui_state(path)
    while True:
        body_control = FormattedTextControl(lambda: [("class:body", _build_main_screen_text(state))])
        result = {"action": "quit"}

        def _toggle_focus() -> None:
            state.focus_section = "apis" if state.focus_section == "models" else "models"

        kb = KeyBindings()

        @kb.add("tab")
        def _(event) -> None:
            _toggle_focus()
            event.app.invalidate()

        @kb.add("s-tab")
        def _(event) -> None:
            _toggle_focus()
            event.app.invalidate()

        @kb.add("enter")
        def _(event) -> None:
            result["action"] = "edit_models" if state.focus_section == "models" else "edit_apis"
            event.app.exit()

        @kb.add("a")
        def _(event) -> None:
            if state.focus_section != "models":
                return
            result["action"] = "add_model"
            event.app.exit()

        @kb.add("e")
        def _(event) -> None:
            result["action"] = "edit_models" if state.focus_section == "models" else "edit_apis"
            event.app.exit()

        @kb.add("c-s")
        def _(event) -> None:
            result["action"] = "save"
            event.app.exit()

        @kb.add("q")
        def _(event) -> None:
            result["action"] = "quit"
            event.app.exit()

        root = HSplit(
            [
                Window(height=1, content=FormattedTextControl([("class:frame", "KittyChain Config")])),
                Window(height=1, char="-", style="class:frame"),
                Window(content=body_control),
            ]
        )
        application = Application(
            layout=Layout(root),
            key_bindings=kb,
            full_screen=False,
            style=_APP_STYLE,
        )
        application.run()

        action = result["action"]
        if action == "save":
            write_config_tui_state(state, path)
            message_dialog(
                title="Config Saved",
                text=f"Saved configuration to:\n{path}",
            ).run()
            return 0
        if action == "quit":
            return 0
        _apply_post_action(state, action)
