"""Read business flow CSV files into a tree-shaped text view."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from _internal_csv import filter_rows, load_csv_rows  # type: ignore
else:
    from ._internal_csv import filter_rows, load_csv_rows
    from .base import Tool


class ReadFlowTool(Tool):
    name = "read_flow"
    description = "读取策略工作流 CSV，并返回按节点分支展示的文本工作流。"
    parameters = {
        "type": "object",
        "properties": {
            "biz_flow_csv": {"type": "string", "description": "biz_flow CSV 文件路径"},
            "biz_type": {"type": "string", "description": "可选业务类型过滤，如 register"},
        },
        "required": ["biz_flow_csv"],
    }

    def execute(self, biz_flow_csv: str, biz_type: str | None = None) -> str:
        rows = filter_rows(load_csv_rows(biz_flow_csv), biz_type=biz_type)
        if not rows:
            return "Error: no matching biz flow rows found"

        row = rows[0]
        payload = json.loads(row.get("extend") or "{}")
        nodes = payload.get("nodes") or []
        edges = payload.get("edges") or []
        if not nodes:
            return "Error: workflow has no nodes"

        node_map = {node.get("id"): node for node in nodes if node.get("id")}
        children: dict[str, list[str]] = defaultdict(list)
        incoming: set[str] = set()
        for edge in sorted(edges, key=lambda item: item.get("index", 0)):
            source = edge.get("source")
            target = edge.get("target")
            if source in node_map and target in node_map:
                children[source].append(target)
                incoming.add(target)

        roots = [node_id for node_id, node in node_map.items() if node_id not in incoming]
        roots.sort(key=lambda node_id: (node_map[node_id].get("index", 0), node_map[node_id].get("label", "")))

        lines = [f"{row.get('biz_name') or row.get('biz_type') or 'workflow'} 工作流"]
        for root_index, root_id in enumerate(roots):
            if root_index:
                lines.append("")
            lines.extend(_render_tree(root_id, node_map, children, prefix="", seen=set()))
        return "\n".join(lines)


def _render_tree(node_id: str, node_map: dict[str, dict], children: dict[str, list[str]], prefix: str, seen: set[str]) -> list[str]:
    node = node_map[node_id]
    label = node.get("label") or node_id
    operator = node.get("operatorType") or "UNKNOWN"
    line = f"{prefix}{label} [{operator}]"
    lines = [line]
    if node_id in seen:
        return lines

    next_seen = set(seen)
    next_seen.add(node_id)
    child_ids = children.get(node_id, [])
    for index, child_id in enumerate(child_ids):
        branch = "└─ " if index == len(child_ids) - 1 else "├─ "
        extension = "   " if index == len(child_ids) - 1 else "│  "
        lines.extend(_render_tree(child_id, node_map, children, prefix + branch, next_seen))
        if index != len(child_ids) - 1 and children.get(child_id):
            continue
    return lines


def main(biz_flow_csv: str, biz_type: str | None = None) -> int:
    output = ReadFlowTool().execute(biz_flow_csv=biz_flow_csv, biz_type=biz_type)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("../../demo/data/biz_flow.csv"))
