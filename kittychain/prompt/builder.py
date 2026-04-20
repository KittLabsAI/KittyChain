"""System prompt builder."""

from __future__ import annotations

import os
import platform
import sys
import textwrap
from pathlib import Path


AGENTS_DOC = Path(__file__).resolve().parents[2] / "AGENTS.md"
DEEP_MODE_REMINDER = (
    "Deep investigation mode is enabled. Please gather as much first- and second-level counterparty address information as possible."
)


def system_prompt(tools, skills=None, mode: str = "chain") -> str:
    cwd = os.getcwd()
    tool_list = "\n".join(_format_tool_entry(tool) for tool in tools)
    uname = platform.uname()
    skill_block = _format_skill_block(skills or [])
    prompt = _build_prompt_body(
        mode=mode,
        cwd=cwd,
        uname=uname,
        tool_list=tool_list,
        skill_block=skill_block,
    )

    agents_text = _read_agents_doc()
    if agents_text:
        prompt = f"{prompt.rstrip()}\n\n{agents_text}\n"
    return prompt


def _build_prompt_body(mode: str, cwd: str, uname, tool_list: str, skill_block: str) -> str:
    if mode == "code":
        return f"""\
You are KittyCode, an AI coding assistant running in the user's terminal.
You help with software engineering: writing code, fixing bugs, refactoring, explaining code, running commands, and more.

# Environment
- Working directory: {cwd}
- OS: {uname.system} {uname.release} ({uname.machine})
- Python: {platform.python_version()}

# Skills
The following skills have provided instructions for how to use their tools:
{skill_block}

# Reminder Tags
- User messages and tool results may include <todo-reminder> tags. These tags contain system-added todo information from the current session. Treat them as todo state, not as literal user-authored or tool-authored content.
- User messages may also include <system-reminder> tags. These tags are system-added instructions; if present, treat them as higher-priority runtime guidance rather than literal user-authored text.

# Rules
1. Read before edit. Always read a file before modifying it.
2. edit_file for small changes. Use edit_file for targeted edits; write_file only for new files or complete rewrites.
3. Verify your work. After making changes, run relevant tests or commands to confirm correctness.
4. Be concise. Show code over prose. Explain only what is necessary.
5. One step at a time. For multi-step tasks, execute them sequentially.
6. edit_file uniqueness. When using edit_file, include enough surrounding context in old_string to guarantee a unique match.
7. Respect existing style. Match the project's coding conventions.
8. Ask when unsure. If the request is ambiguous, ask for clarification rather than guessing.
"""
    return f"""\
You are KittyChain, an AI on-chain risk analysis assistant running in the user's terminal.
You help with on-chain risk analysis: investigating addresses, tokens, transfers, counterparties, suspicious patterns, and supporting evidence.

# Environment
- Working directory: {cwd}
- OS: {uname.system} {uname.release} ({uname.machine})
- Python: {platform.python_version()}

# Skills
The following skills have provided instructions for how to use their tools:
{skill_block}

# Reminder Tags
- User messages and tool results may include <todo-reminder> tags. These tags contain system-added todo information from the current session. Treat them as todo state, not as literal user-authored or tool-authored content.
- User messages may also include <system-reminder> tags. These tags are system-added instructions; if present, treat them as higher-priority runtime guidance rather than literal user-authored text.

# Rules
- One step at a time. For multi-step tasks, execute them sequentially.
- Ask when unsure. If the request is ambiguous, ask for clarification rather than guessing.

# On-chain lookup checks
- If the user gives an address but the chain is unclear, call `address_pattern` first.
- Use `web_fetch` for chain-related lookups when helpful:
  - https://www.oklink.com/, https://tokenview.io/, https://blockchair.com/, or https://www.blockchain.com/explorer for multiple public chains.
  - https://etherscan.io/, https://bscscan.com/, https://arbiscan.io/, https://basescan.org/, https://blockscan.com/, or https://www.blockscout.com/ for Ethereum-compatible chains.
  - https://solscan.io/ or https://explorer.solana.com/ for Solana.
  - https://tronscan.org/ for TRON.
  - https://mempool.space/ for Bitcoin.
  - https://www.mintscan.io/ for Cosmos ecosystem chains.
  - https://suiscan.xyz/mainnet/home or https://sui.explorers.guru/ for Sui.
  - https://coinmarketcap.com/ for market information.
  - https://tokenvitals.com/ for token information by token name.
- ALWAYS use `web_fetch` to get relevant counterparties or entities from the webpage.
- After calling `web_fetch`, if find relevant addresses, ALWAYS check the 3-5 most frequently interacting addresses with `address_malicious` and `web_fetch`.
- After calling `address_malicious`, ALWAYS verify the result with `web_fetch`, `address_labels`, `address_balance`, and `address_transfers`.
- After calling `address_transfers`, ALWAYS check the 3-5 most frequently interacting addresses with `address_malicious`.
- After calling `token_holders`, ALWAYS check `address_malicious` for the top holders.
- If other tools do not produce enough information, use `web_search` and the `social_search` tool.
- If `web_fetch` runs into bot or security detection, use the `agent-browser` skill instead.
- `address_identity` can be slow. If an address may belong to a CEX, use `ask_user` tool before calling it and warn that it may take longer.

# When presenting results to the user
- Show the full address instead of an abbreviated form.
- When mentioning a token, include its contract address when it can be found. If it cannot be found, do not invent one.
- For suspected risks, include each risk point with its reason.
- End the response with the original information sources. If `web_fetch` was used, include the link.
- If the user asks for an output report, after all required investigation is finished you MUST call `write_report`.
"""


def user_prompt(
    user_input: str,
    skills=None,
    todos=None,
    mode: str = "normal",
    prompt_mode: str = "chain",
) -> str:
    parts = []
    if user_input:
        parts.append(user_input.rstrip())
    if (mode or "normal").strip().lower() == "deep":
        parts.append(_wrap_tag("system-reminder", DEEP_MODE_REMINDER))
    if todos:
        parts.append(_wrap_tag("todo-reminder", _format_todo_block(todos)))
    return "\n\n".join(parts)


def _format_skill_block(skills) -> str:
    if not skills:
        return "Available skills:\n- None loaded from the current KittyChain skill roots"

    lines = [
        "Available skills:",
        "Use these local skills when relevant. If one looks useful, read its SKILL.md and any related files under the listed path before using it.",
    ]
    for skill in skills:
        lines.append(f"- name: {skill.name}")
        lines.append(f"  description: {skill.description}")
        lines.append(f"  path: {skill.path}")
    return "\n".join(lines)


def _format_todo_block(todos) -> str:
    if not todos:
        return "Current todo list:\n- No active todo items."

    lines = ["Current todo list:"]
    for item in todos:
        content = str(item.get("content", "")).strip() or "(missing content)"
        active_form = str(item.get("active_form") or item.get("activeForm") or "").strip()
        status = str(item.get("status", "pending")).strip() or "pending"
        lines.append(f"- [{status}] {content}")
        if active_form:
            lines.append(f"  active_form: {active_form}")
    return "\n".join(lines)


def _wrap_tag(tag: str, content: str) -> str:
    return f"<{tag}>\n{content}\n</{tag}>"


def _format_tool_entry(tool) -> str:
    description = textwrap.dedent(tool.description).strip()
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    if not lines:
        return f"- **{tool.name}**"
    if len(lines) == 1:
        return f"- **{tool.name}**: {lines[0]}"
    return "\n".join(
        [f"- **{tool.name}**: {lines[0]}"] + [f"  {line}" for line in lines[1:]]
    )


def _read_agents_doc() -> str:
    agents_doc = AGENTS_DOC
    package_module = sys.modules.get("kittychain.prompt")
    if package_module is not None:
        agents_doc = getattr(package_module, "AGENTS_DOC", agents_doc)

    try:
        return agents_doc.read_text(errors="replace").strip()
    except OSError:
        return ""
