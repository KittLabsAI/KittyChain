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
from prompt_toolkit.shortcuts import input_dialog, message_dialog, radiolist_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Dialog

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
    is_default: bool = False


@dataclass
class ConfigTUIState:
    models: list[ConfigTUIModel] = field(default_factory=list)
    apis: ApiConfig = field(default_factory=ApiConfig)
    issue: str | None = None
    max_tokens: int = _DEFAULT_MAX_TOKENS
    temperature: float = _DEFAULT_TEMPERATURE
    max_context: int = _DEFAULT_MAX_CONTEXT
    focus_section: str = "models"
    selected_model_index: int = 0


_FOCUS_ORDER = (
    "models",
    "add_model",
    "delete_model",
    "max_tokens",
    "temperature",
    "max_context",
    "api_key",
    "save",
    "cancel",
)


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

    try:
        config = Config.from_file(path)
    except ValueError as exc:
        return ConfigTUIState(
            issue=f"Config needs repair:\n{exc}",
            max_tokens=max_tokens,
            temperature=temperature,
            max_context=max_context,
        )

    issue = None
    if not path.exists():
        issue = f"Config file not found: {path}\nUse this screen to create one."

    return ConfigTUIState(
        models=[
            ConfigTUIModel(
                provider=model.provider,
                interface=model.interface,
                api_key=model.api_key,
                model_name=model.model_name,
                base_url=model.base_url or "",
                is_default=model.is_default,
            )
            for model in config.models
        ],
        apis=config.apis,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        max_context=config.max_context_tokens,
        issue=issue,
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


def render_model_list(models: list[ConfigTUIModel], selected_index: int = 0) -> str:
    def _display_provider(model: ConfigTUIModel) -> str:
        return f"{model.provider} (default)" if model.is_default else model.provider

    provider_width = max(len("Provider"), *(len(_display_provider(m)) for m in models)) if models else len("Provider")
    model_width = max(len("Model"), *(len(model.model_name) for model in models)) if models else len("Model")
    base_width = max(len("Base URL"), *(len(model.base_url) for model in models)) if models else len("Base URL")

    header = f"   {'Provider':<{provider_width}} | {'Model':<{model_width}} | {'Base URL':<{base_width}}"
    divider = f"   {'-' * provider_width}-+-{'-' * model_width}-+-{'-' * base_width}"
    if not models:
        return "\n".join([header, divider, "(no models configured yet)"])

    rows = [
        f"{'>' if index == selected_index else ' '}  {_display_provider(model):<{provider_width}} | "
        f"{model.model_name:<{model_width}} | {model.base_url:<{base_width}}"
        for index, model in enumerate(models)
    ]
    return "\n".join([header, divider, *rows])


def mask_secret(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 4:
        return value
    return f"{value[:4]}...{value[-4:]}"


def render_api_summary(apis: ApiConfig) -> str:
    return f"KITTYCHAIN_API_KEY: {mask_secret(apis.kittychain_api_key)}"


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
                is_default=model.is_default,
            )
            for model in state.models
        ],
        apis=ApiConfig(kittychain_api_key=state.apis.kittychain_api_key),
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


def _select_model_index(
    models: list[ConfigTUIModel],
    *,
    title: str = "Edit Model",
    text: str = "Choose an existing model to edit.",
) -> int | None:
    if not models:
        message_dialog(
            title=title,
            text="No configured models yet. Add one first.",
        ).run()
        return None

    values = [
        (index, f"{model.provider} | {model.model_name} | {model.base_url}")
        for index, model in enumerate(models)
    ]
    return radiolist_dialog(
        title=title,
        text=text,
        values=values,
        default=values[0][0],
    ).run()


def _edit_apis(existing: ApiConfig, prompt_text=_prompt_text) -> ApiConfig | None:
    api_key = prompt_text("API Config", "KITTYCHAIN_API_KEY", existing.kittychain_api_key)
    if api_key is None:
        return None
    return ApiConfig(kittychain_api_key=api_key)


def _focus_marker(state: ConfigTUIState, section: str, label: str) -> str:
    return f"> {label}" if state.focus_section == section else f"  {label}"


def _focus_button(state: ConfigTUIState, section: str, label: str) -> str:
    return f">{label}<" if state.focus_section == section else label


def _build_main_screen_text(state: ConfigTUIState) -> str:
    lines: list[str] = []
    if state.issue:
        lines.extend([state.issue, ""])
    lines.extend(
        [
            "Models",
            render_model_list(state.models, state.selected_model_index),
            "",
            f"{_focus_button(state, 'add_model', '[Add]')} {_focus_button(state, 'delete_model', '[Delete]')}",
            "",
            "Model Global Settings",
            _focus_marker(state, "max_tokens", f"max_tokens: {state.max_tokens}"),
            _focus_marker(state, "temperature", f"temperature: {state.temperature}"),
            _focus_marker(state, "max_context", f"max_context: {state.max_context}"),
            "",
            "API KEY",
            _focus_marker(state, "api_key", render_api_summary(state.apis)),
            "",
            f"{_focus_button(state, 'save', '[Save]')} {_focus_button(state, 'cancel', '[Cancel]')}",
            "",
            "Up/Down: select model | Enter: select | e: edit | Ctrl-S: save | q: quit",
        ]
    )
    return "\n".join(lines)


def _focus_relative(state: ConfigTUIState, offset: int) -> None:
    current = _FOCUS_ORDER.index(state.focus_section) if state.focus_section in _FOCUS_ORDER else 0
    state.focus_section = _FOCUS_ORDER[(current + offset) % len(_FOCUS_ORDER)]


def _move_focus_down(state: ConfigTUIState) -> None:
    if state.focus_section == "models" and state.models:
        if state.selected_model_index < len(state.models) - 1:
            state.selected_model_index += 1
            return
        state.focus_section = "add_model"
        return
    _focus_relative(state, 1)


def _move_focus_up(state: ConfigTUIState) -> None:
    if state.focus_section == "models" and state.models and state.selected_model_index > 0:
        state.selected_model_index -= 1
        return
    _focus_relative(state, -1)


def _selected_model_index(state: ConfigTUIState) -> int | None:
    if not state.models:
        return None
    state.selected_model_index = max(0, min(state.selected_model_index, len(state.models) - 1))
    return state.selected_model_index


def _edit_number_setting(
    state: ConfigTUIState,
    attr: str,
    label: str,
    cast,
    *,
    prompt_text=_prompt_text,
) -> bool:
    raw_value = prompt_text("Model Global Settings", label, str(getattr(state, attr)))
    if raw_value is None:
        return False
    try:
        setattr(state, attr, cast(raw_value))
    except ValueError:
        state.issue = f"{label} must be a valid {cast.__name__}"
        return False
    state.issue = None
    return True


def _apply_post_action(
    state: ConfigTUIState,
    action: str,
    *,
    edit_model=_edit_model,
    edit_apis=_edit_apis,
    select_model_index=_select_model_index,
    prompt_text=_prompt_text,
) -> bool:
    if action == "add_model":
        updated = edit_model()
        if updated is None:
            return False
        state.models.append(updated)
        state.selected_model_index = len(state.models) - 1
        state.issue = None
        return True

    if action in {"edit_model", "edit_models"}:
        index = _selected_model_index(state)
        if index is None:
            updated = edit_model()
            if updated is None:
                return False
            state.models.append(updated)
            state.selected_model_index = 0
            state.issue = None
            return True

        if state.models[index].is_default:
            state.issue = "Default model cannot be edited."
            return False

        updated = edit_model(state.models[index])
        if updated is None:
            return False
        state.models[index] = updated
        state.issue = None
        return True

    if action == "activate_model":
        index = _selected_model_index(state)
        if index is None:
            return False
        selected = state.models.pop(index)
        state.models.insert(0, selected)
        state.selected_model_index = 0
        state.issue = None
        return True

    if action == "delete_model":
        deletable = [m for m in state.models if not m.is_default]
        if not deletable:
            state.issue = "Default model cannot be deleted."
            return False

        try:
            deletable_index = select_model_index(
                deletable,
                title="Delete Model",
                text="Choose an existing model to delete.",
            )
        except TypeError:
            deletable_index = select_model_index(deletable)
        if deletable_index is None:
            return False
        selected = deletable[deletable_index]
        original_index = state.models.index(selected)
        del state.models[original_index]
        state.selected_model_index = max(0, min(original_index, len(state.models) - 1))
        state.issue = None
        return True

    if action in {"edit_api_key", "edit_apis"}:
        updated = edit_apis(state.apis)
        if updated is None:
            return False
        state.apis = updated
        state.issue = None
        return True

    if action == "edit_max_tokens":
        return _edit_number_setting(state, "max_tokens", "max_tokens", int, prompt_text=prompt_text)

    if action == "edit_temperature":
        return _edit_number_setting(state, "temperature", "temperature", float, prompt_text=prompt_text)

    if action == "edit_max_context":
        return _edit_number_setting(state, "max_context", "max_context", int, prompt_text=prompt_text)

    return False


def run_config_tui(config_path: Path | str | None = None) -> int:
    path = Path(config_path).expanduser() if config_path is not None else CONFIG_PATH
    state = load_config_tui_state(path)
    while True:
        result = {"action": "quit"}

        kb = KeyBindings()

        @kb.add("tab")
        def _(event) -> None:
            _focus_relative(state, 1)
            event.app.invalidate()

        @kb.add("s-tab")
        def _(event) -> None:
            _focus_relative(state, -1)
            event.app.invalidate()

        @kb.add("down")
        def _(event) -> None:
            _move_focus_down(state)
            event.app.invalidate()

        @kb.add("up")
        def _(event) -> None:
            _move_focus_up(state)
            event.app.invalidate()

        @kb.add("enter")
        def _(event) -> None:
            actions = {
                "models": "activate_model",
                "add_model": "add_model",
                "delete_model": "delete_model",
                "max_tokens": "edit_max_tokens",
                "temperature": "edit_temperature",
                "max_context": "edit_max_context",
                "api_key": "edit_api_key",
                "save": "save",
                "cancel": "quit",
            }
            result["action"] = actions.get(state.focus_section, "quit")
            event.app.exit()

        @kb.add("e")
        def _(event) -> None:
            result["action"] = "edit_model"
            event.app.exit()

        @kb.add("c-s")
        def _(event) -> None:
            result["action"] = "save"
            event.app.exit()

        @kb.add("q")
        def _(event) -> None:
            result["action"] = "quit"
            event.app.exit()

        body_control = FormattedTextControl(
            lambda: [("class:body", _build_main_screen_text(state))],
            focusable=True,
            key_bindings=kb,
            show_cursor=False,
        )
        body_window = Window(content=body_control)

        root = Dialog(
            title="KittyChain Config",
            body=HSplit([body_window]),
            buttons=[],
            with_background=True,
        )
        application = Application(
            layout=Layout(root, focused_element=body_window),
            key_bindings=kb,
            full_screen=True,
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
