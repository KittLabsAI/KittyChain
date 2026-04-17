"""Tool definition for web_browser."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from ..base import Tool

from .core import (
    _close_session,
    _fetch_status_code,
    _normalize_url,
    _run_agent_browser,
    cleanup_stale_sessions,
    format_error,
    format_success,
    remove_session,
    touch_session,
)
from .parsing import extract_page_text, parse_snapshot_output
from .summarize import _summarize_with_llm


class WebBrowserTool(Tool):
    name = "web_browser"
    description = """
Control a real browser through agent-browser. Use `action` to open pages, inspect elements,
wait for conditions, capture screenshots, export PDFs, and fetch page content for summaries.

# Important Notes
- Prefer the action interface: `open`, `snapshot`, `get`, `wait`, `screenshot`, `pdf`, and related browser actions.
- ALWAYS use this after calling other tools like address_malicious to verify their results by fetching relevant web pages.
- If this tool fails, use `agent-browser` skill instead.
- ALWAYS try to get relevant counterparties or entities from webpage.
- After calling this tool, if find relevant addresses, ALWAYS check the 3-5 most frequently interacting addresses with `address_malicious` and `web_browser`.
- If timeout, try again with a longer timeout.

# Important Webpage
- https://www.oklink.com/, https://tokenview.io/, https://blockchair.com/, or https://www.blockchain.com/explorer for multiple public chains.
- https://etherscan.io/, https://bscscan.com/, https://arbiscan.io/, https://basescan.org/, https://blockscan.com/, or https://www.blockscout.com/ for Ethereum-compatible chains.
- https://solscan.io/ or https://explorer.solana.com/ for Solana.
- https://tronscan.org/ for TRON.
- https://mempool.space/ for Bitcoin.
- https://www.mintscan.io/ for Cosmos ecosystem chains.
- https://suiscan.xyz/mainnet/home or https://sui.explorers.guru/ for Sui.
- https://coinmarketcap.com/ for market information.
- https://tokenvitals.com/ for token information by token name.

# Essential Commands

```bash
# Navigation
agent-browser open <url>              # Navigate (aliases: goto, navigate)
agent-browser close                   # Close browser

# Snapshot
agent-browser snapshot -i             # Interactive elements with refs (recommended)
agent-browser snapshot -s "#selector" # Scope to CSS selector

# Interaction (use @refs from snapshot)
agent-browser click @e1               # Click element
agent-browser click @e1 --new-tab     # Click and open in new tab
agent-browser fill @e2 "text"         # Clear and type text
agent-browser type @e2 "text"         # Type without clearing
agent-browser select @e1 "option"     # Select dropdown option
agent-browser check @e1               # Check checkbox
agent-browser press Enter             # Press key
agent-browser keyboard type "text"    # Type at current focus (no selector)
agent-browser keyboard inserttext "text"  # Insert without key events
agent-browser scroll down 500         # Scroll page
agent-browser scroll down 500 --selector "div.content"  # Scroll within a specific container

# Get information
agent-browser get text @e1            # Get element text
agent-browser get url                 # Get current URL
agent-browser get title               # Get page title
agent-browser get cdp-url             # Get CDP WebSocket URL

# Wait
agent-browser wait @e1                # Wait for element
agent-browser wait --load networkidle # Wait for network idle
agent-browser wait --url "**/page"    # Wait for URL pattern
agent-browser wait 2000               # Wait milliseconds
agent-browser wait --text "Welcome"    # Wait for text to appear (substring match)
agent-browser wait --fn "!document.body.innerText.includes('Loading...')"  # Wait for text to disappear
agent-browser wait "#spinner" --state hidden  # Wait for element to disappear

# Downloads
agent-browser download @e1 ./file.pdf          # Click element to trigger download
agent-browser wait --download ./output.zip     # Wait for any download to complete
agent-browser --download-path ./downloads open <url>  # Set default download directory

# Network
agent-browser network requests                 # Inspect tracked requests
agent-browser network requests --type xhr,fetch  # Filter by resource type
agent-browser network requests --method POST   # Filter by HTTP method
agent-browser network requests --status 2xx    # Filter by status (200, 2xx, 400-499)
agent-browser network request <requestId>      # View full request/response detail
agent-browser network route "**/api/*" --abort  # Block matching requests
agent-browser network har start                # Start HAR recording
agent-browser network har stop ./capture.har   # Stop and save HAR file

# Viewport & Device Emulation
agent-browser set viewport 1920 1080          # Set viewport size (default: 1280x720)
agent-browser set viewport 1920 1080 2        # 2x retina (same CSS size, higher res screenshots)
agent-browser set device "iPhone 14"          # Emulate device (viewport + user agent)

# Capture
agent-browser screenshot              # Screenshot to temp dir
agent-browser screenshot --full       # Full page screenshot
agent-browser screenshot --annotate   # Annotated screenshot with numbered element labels
agent-browser screenshot --screenshot-dir ./shots  # Save to custom directory
agent-browser screenshot --screenshot-format jpeg --screenshot-quality 80
agent-browser pdf output.pdf          # Save as PDF

# Live preview / streaming
agent-browser stream enable           # Start runtime WebSocket streaming on an auto-selected port
agent-browser stream enable --port 9223  # Bind a specific localhost port
agent-browser stream status           # Inspect enabled state, port, connection, and screencasting
agent-browser stream disable          # Stop runtime streaming and remove the .stream metadata file

# Clipboard
agent-browser clipboard read                      # Read text from clipboard
agent-browser clipboard write "Hello, World!"     # Write text to clipboard
agent-browser clipboard copy                      # Copy current selection
agent-browser clipboard paste                     # Paste from clipboard

# Dialogs (alert, confirm, prompt)
agent-browser dialog accept              # Accept dialog
agent-browser dialog accept "my input"   # Accept prompt dialog with text
agent-browser dialog dismiss             # Dismiss/cancel dialog
agent-browser dialog status              # Check if a dialog is currently open

# Diff (compare page states)
agent-browser diff snapshot                          # Compare current vs last snapshot
agent-browser diff snapshot --baseline before.txt    # Compare current vs saved file
agent-browser diff screenshot --baseline before.png  # Visual pixel diff
agent-browser diff url <url1> <url2>                 # Compare two pages
agent-browser diff url <url1> <url2> --wait-until networkidle  # Custom wait strategy
agent-browser diff url <url1> <url2> --selector "#main"  # Scope to element
```
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Browser action to perform",
                "enum": [
                    "open",
                    "close",
                    "snapshot",
                    "get",
                    "is_visible",
                    "is_enabled",
                    "is_checked",
                    "wait",
                    "wait_download",
                    "screenshot",
                    "pdf",
                    "click",
                    "fill",
                    "type",
                    "scroll",
                    "scrollinto",
                    "select",
                ],
            },
            "session": {
                "type": "string",
                "description": "Required named session to reuse browser state across calls",
            },
            "url": {
                "type": "string",
                "description": "URL for open",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 120)",
            },
            "intent": {
                "type": "string",
                "description": "Optional summary intent for open/get results",
            },
            "target": {
                "type": "string",
                "description": "Target property for get actions, such as text/url/title/value/html/attr",
            },
            "ref": {
                "type": "string",
                "description": "Element ref like @e1 for element-scoped actions",
            },
            "value": {
                "type": "string",
                "description": "Action-specific value, such as wait target text/load state or input text",
            },
            "scope": {
                "type": "string",
                "description": "CSS selector scope for snapshot",
            },
            "compact": {
                "type": "boolean",
                "description": "Use compact snapshot output",
            },
            "depth": {
                "type": "integer",
                "description": "Snapshot depth limit",
            },
            "wait_type": {
                "type": "string",
                "description": "Wait type such as load/text/url/element/milliseconds/javascript/selector_state",
            },
            "path": {
                "type": "string",
                "description": "Output path for screenshot/pdf/download wait",
            },
            "full": {
                "type": "boolean",
                "description": "Use full page screenshot",
            },
            "direction": {
                "type": "string",
                "description": "Scroll direction such as up or down",
            },
            "pixels": {
                "type": "integer",
                "description": "Scroll distance in pixels",
            },
            "selector": {
                "type": "string",
                "description": "Optional selector for scoped scroll",
            },
        },
        "required": ["action", "session"],
    }

    def execute(self, *args, **kwargs) -> str:
        action = kwargs.pop("action", args[0] if args else None)
        url = kwargs.pop("url", "")
        timeout = int(kwargs.pop("timeout", 20))
        session = kwargs.pop("session", None)
        intent = kwargs.pop("intent", "")
        if not session:
            return format_error(action or "unknown", "invalid_arguments", "session is required")
        if action:
            try:
                cleanup_stale_sessions(timeout=timeout)
                return self._execute_action(action=action, timeout=timeout, session=session, url=url, intent=intent, **kwargs)
            except RuntimeError as exc:
                if "timed out" in str(exc).lower():
                    return format_error(action, "timeout", str(exc), suggestion="Increase timeout or use wait.")
                return format_error(action, "command_failed", str(exc))
        return format_error("unknown", "invalid_action", "action is required")

    def _execute_action(self, action: str, timeout: int, session: str | None, url: str = "", intent: str = "", **kwargs) -> str:
        dispatch = {
            "open": self._action_open,
            "close": self._action_close,
            "snapshot": self._action_snapshot,
            "get": self._action_get,
            "is_visible": self._action_is_visible,
            "is_enabled": self._action_is_enabled,
            "is_checked": self._action_is_checked,
            "wait": self._action_wait,
            "wait_download": self._action_wait_download,
            "screenshot": self._action_screenshot,
            "pdf": self._action_pdf,
            "click": self._action_click,
            "fill": self._action_fill,
            "type": self._action_type,
            "scroll": self._action_scroll,
            "scrollinto": self._action_scrollinto,
            "select": self._action_select,
        }
        handler = dispatch.get(action)
        if handler is None:
            return format_error(action, "invalid_action", f"Unsupported action: {action}")
        return handler(timeout=timeout, session=session, url=url, intent=intent, **kwargs)

    def _resolve_session(self, session: str | None) -> str:
        if not session:
            raise ValueError("session is required")
        return session

    def _action_open(self, timeout: int, session: str | None, url: str = "", intent: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        normalized = _normalize_url(url)
        _run_agent_browser(resolved_session, timeout, "open", normalized)
        final_url = _run_agent_browser(resolved_session, timeout, "get", "url")
        title = _run_agent_browser(resolved_session, timeout, "get", "title")
        extra = {}
        if intent:
            text = extract_page_text(
                _run_agent_browser(
                    resolved_session,
                    timeout,
                    "eval",
                    "document.body ? (document.body.innerText || '') : "
                    "(document.documentElement ? (document.documentElement.innerText || '') : '')",
                )
            )
            status_code = _fetch_status_code(resolved_session, timeout)
            extra["summary"] = _summarize_with_llm(
                agent=getattr(self, "_parent_agent", None),
                url=final_url or normalized,
                status_code=status_code,
                prompt=intent,
                page_text=text,
            )
        return format_success(
            "open",
            resolved_session,
            {
                "url": normalized,
                "final_url": final_url,
                "title": title,
                "redirected": final_url != normalized,
            },
            **extra,
        )

    def _action_close(self, timeout: int, session: str | None, **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        _close_session(resolved_session, timeout)
        remove_session(resolved_session)
        return format_success("close", resolved_session, {"closed": True})

    def _action_snapshot(self, timeout: int, session: str | None, scope: str = "", compact: bool = False, depth: int | None = None, **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        args = ["snapshot", "-i"]
        if compact:
            args.append("-c")
        if depth is not None:
            args += ["-d", str(depth)]
        if scope:
            args += ["-s", scope]
        output = _run_agent_browser(resolved_session, timeout, *args)
        current_url = _run_agent_browser(resolved_session, timeout, "get", "url")
        title = _run_agent_browser(resolved_session, timeout, "get", "title")
        return format_success(
            "snapshot",
            resolved_session,
            {
                "url": current_url,
                "title": title,
                "elements": parse_snapshot_output(output),
            },
        )

    def _action_get(self, timeout: int, session: str | None, target: str = "", ref: str = "", value: str = "", intent: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        args = ["get", target]
        if ref:
            args.append(ref)
        if target == "attr" and value:
            args.append(value)
        output = _run_agent_browser(resolved_session, timeout, *args)
        extra = {}
        if intent:
            current_url = output if target == "url" else _run_agent_browser(resolved_session, timeout, "get", "url")
            extra["summary"] = _summarize_with_llm(
                agent=getattr(self, "_parent_agent", None),
                url=current_url,
                status_code="unknown",
                prompt=intent,
                page_text=output,
            )
        return format_success("get", resolved_session, {"target": target, "ref": ref or None, "value": output}, **extra)

    def _run_is_action(self, action: str, check_name: str, timeout: int, session: str | None, ref: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "is", check_name, ref)
        result = output.strip().casefold() in {"true", "1", "yes", "ok"}
        return format_success(action, resolved_session, {"ref": ref, "result": result})

    def _action_is_visible(self, **kwargs) -> str:
        return self._run_is_action("is_visible", "visible", **kwargs)

    def _action_is_enabled(self, **kwargs) -> str:
        return self._run_is_action("is_enabled", "enabled", **kwargs)

    def _action_is_checked(self, **kwargs) -> str:
        return self._run_is_action("is_checked", "checked", **kwargs)

    def _action_wait(self, timeout: int, session: str | None, wait_type: str = "", value: str = "", ref: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        args = ["wait"]
        if wait_type == "load":
            args += ["--load", value]
        elif wait_type == "url":
            args += ["--url", value]
        elif wait_type == "text":
            args += ["--text", value]
        elif wait_type == "javascript":
            args += ["--fn", value]
        elif wait_type == "milliseconds":
            args.append(str(value))
        elif wait_type == "selector_state":
            args += [ref, "--state", value]
        elif ref:
            args.append(ref)
        else:
            args.append(str(value))
        output = _run_agent_browser(resolved_session, timeout, *args)
        return format_success("wait", resolved_session, {"wait_type": wait_type or "element", "result": output})

    def _action_wait_download(self, timeout: int, session: str | None, path: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "wait", "--download", path)
        return format_success("wait_download", resolved_session, {"path": path, "result": output})

    def _action_screenshot(self, timeout: int, session: str | None, path: str = "", full: bool = False, **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        args = ["screenshot"]
        if path:
            args.append(path)
        if full:
            args.append("--full")
        output = _run_agent_browser(resolved_session, timeout, *args)
        return format_success("screenshot", resolved_session, {"path": path, "full": full, "result": output})

    def _action_pdf(self, timeout: int, session: str | None, path: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "pdf", path)
        return format_success("pdf", resolved_session, {"path": path, "result": output})

    def _action_click(self, timeout: int, session: str | None, ref: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "click", ref)
        return format_success("click", resolved_session, {"ref": ref, "result": output})

    def _action_fill(self, timeout: int, session: str | None, ref: str = "", value: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "fill", ref, value)
        return format_success("fill", resolved_session, {"ref": ref, "value": value, "result": output})

    def _action_type(self, timeout: int, session: str | None, ref: str = "", value: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "type", ref, value)
        return format_success("type", resolved_session, {"ref": ref, "value": value, "result": output})

    def _action_scroll(self, timeout: int, session: str | None, direction: str = "down", pixels: int = 300, selector: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        args = ["scroll", direction, str(pixels)]
        if selector:
            args += ["--selector", selector]
        output = _run_agent_browser(resolved_session, timeout, *args)
        return format_success("scroll", resolved_session, {"direction": direction, "pixels": pixels, "selector": selector or None, "result": output})

    def _action_scrollinto(self, timeout: int, session: str | None, ref: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "scrollinto", ref)
        return format_success("scrollinto", resolved_session, {"ref": ref, "result": output})

    def _action_select(self, timeout: int, session: str | None, ref: str = "", value: str = "", **kwargs) -> str:
        resolved_session = self._resolve_session(session)
        touch_session(resolved_session)
        output = _run_agent_browser(resolved_session, timeout, "select", ref, value)
        return format_success("select", resolved_session, {"ref": ref, "value": value, "result": output})


def main(action: str, agent=None, **kwargs) -> int:
    try:
        tool = WebBrowserTool()
        if agent is not None:
            tool.bind_agent(agent)
        output = tool.execute(action=action, **kwargs)
    except Exception as exc:
        output = f"Error: {exc}"
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("open", url="https://example.com", session="demo"))
