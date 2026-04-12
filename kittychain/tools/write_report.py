"""Generate HTML investigation reports with optional relationship graphs."""

from __future__ import annotations

import json
import math
import re
import sys
from html import escape
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from ask_user import AskUserTool  # type: ignore
    from llm.provider import _strip_think_blocks  # type: ignore
else:
    from .base import Tool
    from .ask_user import AskUserTool
    from ..llm.provider import _strip_think_blocks

ADDRESS_RELATIONS = ("hop1-counterparty", "hop2-counterparty", "hop3-counterparty")
NETWORK_INIT_MARKER = "network = new vis.Network(container, data, options);"


class WriteReportTool(Tool):
    name = "write_report"
    description = """
Generate an HTML investigation report and save it to a local file.
Use this after all required evidence has been gathered.
If the user asks for an output report, you MUST call `write_report` after finishing the investigation.
Supports address reports and token reports, with optional deep-mode relevant-address graphs.
    """
    parameters = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["address", "token"],
                "description": "Report type: address or token",
            },
            "mode": {
                "type": "string",
                "enum": ["normal", "deep"],
                "description": "Report depth, defaults to normal",
            },
            "path": {
                "type": "string",
                "description": "Required output path for the generated report HTML file",
            },
            "origin_address": {
                "type": "string",
                "description": "Original address under investigation, required for `address` reports",
            },
            "token_name": {
                "type": "string",
                "description": "Token name, required for `token` reports",
            },
            "token_contract_address": {
                "type": "string",
                "description": "Token contract address, required for `token` reports",
            },
            "top_holders": {
                "type": "array",
                "description": "Top holder rows for `token` reports, required for `token` reports. Each item should include: address, balance, labels, identity, notes",
                "items": {"type": "object"},
            },
            "top_lp_holders": {
                "type": "array",
                "description": "Top LP holder rows for `token` reports, required for `token` reports. Each item should include: address, balance, labels, identity, notes",
                "items": {"type": "object"},
            },
            "relevant_addresses": {
                "type": "array",
                "description": (
                    "Relevant addresses, required for `deep` mode. Each item should include: "
                    "address, balance, labels, identity, relation with origin address or top holders, notes. "
                    "For `type=address`, relation must be one of: hop1-counterparty, "
                    "hop2-counterparty, hop3-counterparty."
                ),
                "items": {"type": "object"},
            },
            "graph_data": {
                "type": "object",
                "description": (
                    "Required for `deep` mode. Format must match: "
                    '`{"node": [{"address": "...", "chain_name": "Ethereum", "address_identity": {...}, '
                    '"address_labels": [...], "address_balance": {...}, "address_malicious": {...}}], '
                    '"edge": [{"source_address": "...", "target_address": "...", "direction": "from", '
                    '"usd_value": 1234, "address_transfers": {...}, "start_time": "...", "end_time": "..."}]}`. '
                    "Each `deep` mode report requires at least 5 nodes and 5 edges."
                ),
            },
            "sources": {
                "type": "array",
                "description": "Information sources used in the report",
                "items": {"type": "string"},
            },
            "content": {
                "type": "string",
                "description": "Main report content and evidence summary",
            },
        },
        "required": ["type", "mode", "path", "sources", "content"],
    }

    def execute(
        self,
        type: str,
        mode: str = "normal",
        path: str = "",
        origin_address: str = "",
        token_name: str = "",
        token_contract_address: str = "",
        top_holders: list[dict[str, Any]] | None = None,
        top_lp_holders: list[dict[str, Any]] | None = None,
        relevant_addresses: list[dict[str, Any]] | None = None,
        graph_data: dict[str, Any] | None = None,
        sources: list[str] | None = None,
        content: str = "",
    ) -> str:
        resolved_mode = resolve_mode(mode, getattr(self, "_parent_agent", None))
        payload = {
            "type": type,
            "mode": resolved_mode,
            "path": path,
            "origin_address": origin_address,
            "token_name": token_name,
            "token_contract_address": token_contract_address,
            "top_holders": top_holders or [],
            "top_lp_holders": top_lp_holders or [],
            "relevant_addresses": relevant_addresses or [],
            "graph_data": graph_data or {},
            "graph_html": "",
            "sources": sources or [],
            "content": content or "",
        }

        skip_payload_validation, ask_user_answer = maybe_confirm_direct_generation(
            payload,
            getattr(self, "_parent_agent", None),
        )

        if ask_user_answer and not skip_payload_validation:
            return ask_user_answer

        if not skip_payload_validation:
            errors = validate_payload(payload, agent=getattr(self, "_parent_agent", None))
            if errors:
                return "Error: " + "; ".join(errors)

        try:
            if payload["graph_data"]:
                payload["graph_html"] = render_graph_html(payload["graph_data"])
            html = generate_report_html(payload, getattr(self, "_parent_agent", None))
            document = wrap_html_document(html, report_title(payload))
            output_path = write_report_file(payload, document)
        except Exception as exc:
            return f"Error: {exc}"

        return f"已经在{output_path}文件输出报告"


def resolve_mode(mode: str | None, agent) -> str:
    normalized = (mode or "").strip().lower()
    if normalized in {"normal", "deep"}:
        return normalized

    if getattr(agent, "deep_mode", False) or getattr(agent, "mode", "") == "deep":
        return "deep"
    return "normal"


def validate_payload(
    payload: dict[str, Any],
    agent=None,
) -> list[str]:
    errors: list[str] = []
    report_type = payload["type"]
    mode = payload["mode"]

    if report_type not in {"address", "token"}:
        errors.append("type must be one of: address, token")

    if mode not in {"normal", "deep"}:
        errors.append("mode must be one of: normal, deep")

    if getattr(agent, "mode", "") == "deep" and mode != "deep":
        errors.append("mode must be deep when agent.mode=deep")

    if not str(payload.get("path", "")).strip():
        errors.append("path is required")

    if report_type == "address" and not str(payload.get("origin_address", "")).strip():
        errors.append("origin_address is required for type=address")

    if report_type == "token":
        if not str(payload.get("token_name", "")).strip():
            errors.append("token_name is required for type=token")
        if not str(payload.get("token_contract_address", "")).strip():
            errors.append("token_contract_address is required for type=token")
        if not is_non_empty_list(payload.get("top_holders")):
            errors.append("top_holders is required for type=token")
        if not is_non_empty_list(payload.get("top_lp_holders")):
            errors.append("top_lp_holders is required for type=token")

    for field_name in ("top_holders", "top_lp_holders", "relevant_addresses"):
        value = payload.get(field_name)
        if value:
            errors.extend(validate_address_rows(value, field_name, report_type=report_type))

    if mode == "deep":
        if not is_non_empty_list(payload.get("relevant_addresses")):
            errors.append("relevant_addresses is required for mode=deep")
        errors.extend(
            validate_graph_data(
                payload.get("graph_data"),
                str(payload.get("origin_address", "")).strip(),
            )
        )

    return errors


def is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def validate_address_rows(rows: Any, field_name: str, *, report_type: str) -> list[str]:
    if not isinstance(rows, list):
        return [f"{field_name} must be a list"]

    errors: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{field_name}[{index}] must be an object")
            continue
        if not str(row.get("address", "")).strip():
            errors.append(f"{field_name}[{index}].address is required")
        if field_name == "relevant_addresses" and report_type == "address":
            relation = str(row.get("relation", "")).strip()
            if relation not in ADDRESS_RELATIONS:
                errors.append(
                    f"{field_name}[{index}].relation must be one of: {', '.join(ADDRESS_RELATIONS)}"
                )
    return errors


def validate_graph_data(graph_data: Any, origin_address: str = "") -> list[str]:
    if not isinstance(graph_data, dict):
        return ["graph_data is required for mode=deep"]

    nodes = graph_data.get("node")
    edges = graph_data.get("edge")
    errors: list[str] = []

    if not isinstance(nodes, list):
        errors.append("graph_data.node must be a list")
    else:
        if len(nodes) < 5:
            errors.append(_graph_shortage_message("nodes", origin_address))
        errors.extend(validate_graph_nodes(nodes))

    if not isinstance(edges, list):
        errors.append("graph_data.edge must be a list")
    else:
        if len(edges) < 5:
            errors.append(_graph_shortage_message("edges", origin_address))
        errors.extend(validate_graph_edges(edges))

    return errors


def _graph_shortage_message(kind: str, origin_address: str) -> str:
    target = origin_address or "the origin address"
    return f"graph_data must include at least 5 {kind}; find more hop1/hop2 counterparties of {target}"


def maybe_confirm_direct_generation(payload: dict[str, Any], agent) -> tuple[bool, str | None]:
    if getattr(agent, "mode", "") != "deep":
        return False, None

    if not needs_more_counterparties(payload):
        return False, None

    answer = _ask_user_to_confirm_direct_generation(agent, payload)
    if answer is None:
        return False, None
    return _confirm_direct_generation(agent, answer), answer


def needs_more_counterparties(payload: dict[str, Any]) -> bool:
    relevant_addresses = payload.get("relevant_addresses") or []
    graph_data = payload.get("graph_data") or {}
    nodes = graph_data.get("node") if isinstance(graph_data, dict) else None
    edges = graph_data.get("edge") if isinstance(graph_data, dict) else None
    return (
        not is_non_empty_list(relevant_addresses)
        or not isinstance(nodes, list)
        or len(nodes) < 5
        or not isinstance(edges, list)
        or len(edges) < 5
    )


def _confirm_direct_generation(agent, answer: str) -> bool:
    llm = getattr(agent, "llm", None)
    if llm is None or not hasattr(llm, "complete"):
        return False

    worker = llm.clone() if hasattr(llm, "clone") else llm
    response = worker.complete(
        [{"role": "user", "content": answer}],
        system=(
            "Summarize the user's intent, answer only `yes` or `no`. "
            "No explanation is needed, just a simple confirmation. "
        ),
    )
    lowered = _strip_think_blocks((response.content or "").strip()).lower()
    return "yes" in lowered


def _ask_user_to_confirm_direct_generation(agent, payload: dict[str, Any]) -> str | None:
    ask_tool = AskUserTool()
    ask_tool.bind_agent(agent)
    tool_output_handler = getattr(agent, "tool_output_handler", None)
    question = (
        f"Deep mode is enabled, but there are not enough counterparties to generate a deep report for "
        f"{payload.get('origin_address') or 'the origin address'}. Generate the report directly with the same payload instead?"
    )
    response = ask_tool.execute(
        [
            {
                "header": "Report Mode",
                "question": question,
            }
        ],
        stream_callback=(
            (lambda text: tool_output_handler("ask_user", text))
            if callable(tool_output_handler)
            else None
        ),
    )
    if response.startswith("Error:") or response == "User declined to answer the questions.":
        return None
    if ": " not in response:
        return None
    return response.rsplit(": ", 1)[-1].strip()


def validate_graph_nodes(nodes: list[Any]) -> list[str]:
    errors: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"graph_data.node[{index}] must be an object")
            continue
        if not str(node.get("address", "")).strip():
            errors.append(f"graph_data.node[{index}].address is required")
        if not str(node.get("chain_name", "")).strip():
            errors.append(f"graph_data.node[{index}].chain_name is required")
    return errors


def validate_graph_edges(edges: list[Any]) -> list[str]:
    errors: list[str] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"graph_data.edge[{index}] must be an object")
            continue
        if not str(edge.get("source_address", "")).strip():
            errors.append(f"graph_data.edge[{index}].source_address is required")
        if not str(edge.get("target_address", "")).strip():
            errors.append(f"graph_data.edge[{index}].target_address is required")
        if str(edge.get("direction", "")).strip() not in {"from", "to"}:
            errors.append(f"graph_data.edge[{index}].direction must be 'from' or 'to'")
    return errors


def _escape_html(value: Any) -> str:
    return escape(str(value), quote=True)


def _short_address(address: str) -> str:
    if len(address) <= 12:
        return address
    return f"{address[:6]}...{address[-4:]}"


def _extract_numeric_value(payload: Any) -> float | None:
    if payload in (None, "", [], {}):
        return None
    if isinstance(payload, (int, float)):
        return float(payload)
    if isinstance(payload, str):
        match = re.search(r"[-+]?\d[\d,]*\.?\d*", payload)
        if match:
            return float(match.group(0).replace(",", ""))
        return None
    if isinstance(payload, list):
        values = [value for item in payload if (value := _extract_numeric_value(item)) is not None]
        return max(values) if values else None
    if isinstance(payload, dict):
        for key in ("usd_value", "usd_amount", "amount_usd", "value_usd", "total_usd", "native_balance", "summary"):
            if key in payload:
                value = _extract_numeric_value(payload[key])
                if value is not None:
                    return value
        values = [value for value in (_extract_numeric_value(item) for item in payload.values()) if value is not None]
        return max(values) if values else None
    return None


def _log_scale(value: float | None, *, minimum: float, maximum: float, base_offset: float = 1.0) -> float:
    if value is None or value <= 0:
        return minimum
    normalized = math.log10(value + base_offset)
    capped = max(0.0, min(normalized / 9.0, 1.0))
    return minimum + (maximum - minimum) * capped


def scale_node_size(address_balance: Any) -> int:
    return round(_log_scale(_extract_numeric_value(address_balance), minimum=18, maximum=38))


def scale_edge_width(payload: Any) -> int:
    return round(_log_scale(_extract_numeric_value(payload), minimum=2, maximum=6))


def _detect_risk_level(node: dict[str, Any]) -> str:
    malicious = node.get("address_malicious")
    if not malicious:
        return "unknown"
    if isinstance(malicious, dict):
        haystack = " ".join(str(value).lower() for value in malicious.values())
    else:
        haystack = str(malicious).lower()
    if "high" in haystack:
        return "high"
    if "medium" in haystack or "mid" in haystack:
        return "medium"
    if "low" in haystack:
        return "low"
    return "unknown"


def _node_color(node: dict[str, Any]) -> dict[str, Any]:
    chain_colors = {
        "Ethereum": {"background": "#dbeafe", "border": "#2563eb"},
        "Base": {"background": "#dbeafe", "border": "#1d4ed8"},
        "Arbitrum": {"background": "#e0f2fe", "border": "#0284c7"},
        "Optimism": {"background": "#fee2e2", "border": "#ef4444"},
        "Polygon": {"background": "#ede9fe", "border": "#7c3aed"},
    }
    risk_colors = {
        "high": "#dc2626",
        "medium": "#f59e0b",
        "low": "#16a34a",
        "unknown": "#94a3b8",
    }
    base = chain_colors.get(node["chain_name"], {"background": "#f8fafc", "border": "#475569"}).copy()
    border = risk_colors[_detect_risk_level(node)]
    base["border"] = border
    base["highlight"] = {"background": base["background"], "border": border}
    return base


def _render_inline_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(_escape_html(item) for item in value)
    if isinstance(value, dict):
        return "<br>".join(f"{_escape_html(key)}: {_escape_html(item)}" for key, item in value.items())
    return _escape_html(value)


def _render_section(title: str, rows: list[tuple[str, Any]]) -> str:
    visible_rows = [(label, value) for label, value in rows if value not in (None, "", [], {})]
    if not visible_rows:
        return ""
    rendered_rows = []
    for label, value in visible_rows:
        rendered_rows.append(
            "<div style='margin:4px 0;'>"
            f"<div style='font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;'>{_escape_html(label)}</div>"
            f"<div style='font-size:13px;color:#0f172a;line-height:1.4;word-break:break-word;overflow-wrap:anywhere;white-space:normal;'>{_render_inline_value(value)}</div>"
            "</div>"
        )
    return (
        "<div style='margin-top:10px;padding-top:8px;border-top:1px solid #e2e8f0;'>"
        f"<div style='font-weight:700;font-size:12px;color:#334155;margin-bottom:4px;'>{_escape_html(title)}</div>"
        f"{''.join(rendered_rows)}"
        "</div>"
    )


def _build_node_title(node: dict[str, Any]) -> str:
    risk_level = _detect_risk_level(node).title()
    return (
        "<div style='min-width:280px;max-width:360px;padding:4px 2px;'>"
        f"<div style='font-size:15px;font-weight:700;color:#0f172a;'>{_short_address(node['address'])}</div>"
        f"<div style='font-size:12px;color:#475569;margin-top:2px;'>{_escape_html(node['chain_name'])}</div>"
        f"<div style='font-size:11px;color:#64748b;margin-top:4px;word-break:break-all;'>{_escape_html(node['address'])}</div>"
        f"{_render_section('Profile', [('Risk Level', risk_level), ('Identity', node.get('address_identity')), ('Labels', node.get('address_labels'))])}"
        f"{_render_section('Balance', [('Address Balance', node.get('address_balance'))])}"
        f"{_render_section('Risk Signals', [('Malicious', node.get('address_malicious'))])}"
        "</div>"
    )


def _build_edge_title(edge: dict[str, Any]) -> str:
    direction = f"{edge['source_address']} -> {edge['target_address']}"
    flow_section = _render_section(
        "Flow",
        [
            ("Direction", direction),
            ("Aggregated USD Value", edge.get("usd_value")),
            ("Address Transfers", edge.get("address_transfers")),
            ("Start Time", edge.get("start_time")),
            ("End Time", edge.get("end_time")),
        ],
    )
    return (
        "<div style='min-width:280px;max-width:360px;padding:4px 2px;'>"
        "<div style='font-size:14px;font-weight:700;color:#0f172a;'>Counterparty relation</div>"
        f"{flow_section}"
        "</div>"
    )


def generate_report_html(payload: dict[str, Any], agent) -> str:
    llm = getattr(agent, "llm", None)
    if llm is None or not hasattr(llm, "complete"):
        raise RuntimeError("write_report requires an agent llm")

    worker = llm.clone() if hasattr(llm, "clone") else llm
    response = worker.complete(
        [
            {
                "role": "user",
                "content": build_user_prompt(payload),
            }
        ],
        system=build_system_prompt(payload),
    )
    content = _strip_think_blocks((response.content or "").strip())
    if not content:
        raise RuntimeError("llm returned empty report content")
    return content


def build_user_prompt(payload: dict[str, Any]) -> str:
    user_payload = {
        "type": payload["type"],
        "mode": payload["mode"],
        "origin_address": payload["origin_address"],
        "token_name": payload["token_name"],
        "token_contract_address": payload["token_contract_address"],
        "top_holders": payload["top_holders"],
        "top_lp_holders": payload["top_lp_holders"],
        "relevant_addresses": payload["relevant_addresses"],
        "graph_html": payload.get("graph_html", ""),
        "sources": payload["sources"],
        "content": payload["content"],
    }
    return (
        "Generate an HTML investigation report based on the following JSON payload.\n"
        "Return HTML only, without markdown fences.\n\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )


def build_system_prompt(payload: dict[str, Any]) -> str:
    detail_hint = "If the report mode is `deep`, make it thorough." if payload["mode"] == "deep" else ""
    common = (
        "You are writing a polished HTML report for an on-chain investigation.\n"
        "Return valid HTML fragments only.\n"
        "Use clear section headings and concise, evidence-based language.\n"
        "If the user asks to output a report, after all information is gathered you must call write_report.\n"
        f"{detail_hint}\n"
    )
    if payload["type"] == "address":
        return common + (
            "The report must include these sections in order:\n"
            "1. Summary\n"
            "2. Risk Overview\n"
            "3. Asset Overview\n"
            "4. Transaction Overview\n"
            "5. Relevant Addresses (if relevant_addresses is not empty), as an HTML table with columns: "
            "Address, Balance, Labels, Identity, Relation, Notes\n"
            "6. Association Graph (if graph_html is provided), use the graph_html code from the user prompt directly\n"
            "7. Sources\n"
        )
    return common + (
        "The report must include these sections in order:\n"
        "1. Summary\n"
        "2. Risk Overview\n"
        "3. Top Holders Overview\n"
        "4. Top LP Holders Overview\n"
        "5. Relevant Addresses (if relevant_addresses is not empty), as an HTML table with columns: "
        "Address, Balance, Labels, Identity, Relation, Notes\n"
        "6. Association Graph (if graph_html is provided), use the graph_html code from the user prompt directly\n"
        "7. Sources\n"
    )


def has_relevant_addresses_section(html: str) -> bool:
    return bool(re.search(r"<h[1-6][^>]*>\s*Relevant Addresses\s*</h[1-6]>", html, flags=re.IGNORECASE))


def append_graph_to_relevant_addresses(html: str, graph_html: str) -> str:
    heading_pattern = re.compile(
        r"(<h[1-6][^>]*>\s*Relevant Addresses\s*</h[1-6]>)(.*?)(?=<h[1-6][^>]*>|$)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = heading_pattern.search(html)
    if not match:
        return html

    replacement = f"{match.group(1)}{match.group(2)}{graph_html}"
    return html[: match.start()] + replacement + html[match.end() :]


def render_graph_html(graph_data: dict[str, Any]) -> str:
    try:
        from pyvis.network import Network
    except ImportError as exc:
        raise RuntimeError("pyvis is required to render graph_data") from exc

    network = Network(height="860px", width="100%", directed=True, bgcolor="#ffffff", font_color="#1f2937")
    if hasattr(network, "set_options"):
        network.set_options(
            """
            const options = {
              "nodes": {
                "shape": "dot",
                "size": 18,
                "font": {"face": "Arial", "size": 14}
              },
              "edges": {
                "color": {"color": "#6b7280", "highlight": "#ef4444"},
                "smooth": {"type": "dynamic"}
              },
              "physics": {
                "barnesHut": {
                  "gravitationalConstant": -2000,
                  "springLength": 180
                },
                "minVelocity": 0.75
              },
              "interaction": {
                "hover": true,
                "navigationButtons": true
              }
            }
            """
        )
    network.barnes_hut()

    for node in graph_data.get("node", []):
        if not isinstance(node, dict):
            continue
        address = node.get("address")
        if not address or not node.get("chain_name"):
            continue
        identity = node.get("address_identity")
        if isinstance(identity, dict):
            identity_summary = next((str(value) for value in identity.values() if value), None)
        else:
            identity_summary = str(identity) if identity else None
        labels = node.get("address_labels") or []
        label_suffix = identity_summary or (labels[0] if labels else node["chain_name"])
        label = f"{_short_address(address)}\n{str(label_suffix)[:22]}"
        network.add_node(
            address,
            label=label,
            title=_build_node_title(node),
            group=node["chain_name"],
            color=_node_color(node),
            size=scale_node_size(node.get("address_balance")),
            borderWidth=3,
            font={"face": "Arial", "size": 15, "multi": "html"},
        )

    for index, edge in enumerate(graph_data.get("edge", []), start=1):
        if not isinstance(edge, dict):
            continue
        source = edge.get("source_address")
        target = edge.get("target_address")
        if source is None or target is None:
            continue
        network.add_edge(
            str(source),
            str(target),
            id=f"edge-{index}",
            title=_build_edge_title(edge),
            arrows="to",
            color="#2563eb",
            width=scale_edge_width(edge.get("usd_value") or edge.get("address_transfers")),
            dashes=False,
            font={"align": "top"},
        )

    raw_html = network.generate_html(notebook=False)
    raw_html = _inject_html_tooltips_markup(raw_html)
    body_match = re.search(r"<body[^>]*>(.*)</body>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    body_html = body_match.group(1).strip() if body_match else raw_html
    return f'<section class="relationship-graph">{body_html}</section>'
def _inject_html_tooltips_markup(html: str) -> str:
    if "function htmlTitle(html)" in html:
        return html
    tooltip_script = """
              function htmlTitle(html) {
                  const container = document.createElement("div");
                  container.innerHTML = html;
                  return container;
              }

              nodes.forEach(function(node) {
                  if (typeof node.title === "string" && node.title.indexOf("<") !== -1) {
                      nodes.update({id: node.id, title: htmlTitle(node.title)});
                  }
              });

              edges.forEach(function(edge) {
                  if (typeof edge.title === "string" && edge.title.indexOf("<") !== -1) {
                      edges.update({id: edge.id, title: htmlTitle(edge.title)});
                  }
              });

"""
    if NETWORK_INIT_MARKER not in html:
        return html
    return html.replace(NETWORK_INIT_MARKER, tooltip_script + NETWORK_INIT_MARKER, 1)


def wrap_html_document(body_html: str, title: str) -> str:
    if "<html" in body_html.lower():
        return body_html

    safe_title = escape(title)
    include_graph_assets = _requires_vis_network_assets(body_html)
    graph_assets = ""
    graph_styles = ""
    if include_graph_assets:
        graph_assets = """
  <link rel="stylesheet" href="https://unpkg.com/vis-network/styles/vis-network.min.css" type="text/css">
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>"""
        graph_styles = """
    .relationship-graph .card {
      border: 1px solid #d8e0ec;
      border-radius: 16px;
      overflow: hidden;
      background: #ffffff;
      margin-top: 16px;
    }
    .relationship-graph .card-body {
      padding: 0;
    }
    #mynetwork {
      width: 100%;
      height: 860px;
      min-height: 860px;
      background: #ffffff;
    }"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>{graph_assets}
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7fb;
      color: #172033;
    }}
    main {{
      max-width: 1080px;
      margin: 32px auto;
      background: #ffffff;
      border-radius: 16px;
      box-shadow: 0 16px 40px rgba(23, 32, 51, 0.08);
      padding: 32px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0 24px;
    }}
    th, td {{
      border: 1px solid #d8e0ec;
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #eef4ff;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
    }}{graph_styles}
  </style>
</head>
<body>
  <main>
{body_html}
  </main>
</body>
</html>
"""


def _requires_vis_network_assets(body_html: str) -> bool:
    html = body_html.lower()
    return (
        "relationship-graph" in html
        or "new vis.network" in html
        or "vis.dataset" in html
        or 'id="mynetwork"' in html
    )


def write_report_file(payload: dict[str, Any], document: str) -> Path:
    output_path = Path(str(payload["path"])).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def report_title(payload: dict[str, Any]) -> str:
    if payload["type"] == "address":
        return f"Address Report - {payload['origin_address']}"
    return f"Token Report - {payload['token_name'] or payload['token_contract_address']}"


def main() -> int:
    print("Use this tool from the agent runtime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
