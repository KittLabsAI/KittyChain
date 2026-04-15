"""Read node rules from CSV into grouped text output."""

from __future__ import annotations

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


class ReadNodeTool(Tool):
    name = "read_node"
    description = "读取节点规则 CSV，按节点聚合展示规则、状态、策略结果和原因码。"
    parameters = {
        "type": "object",
        "properties": {
            "node_rules_csv": {"type": "string", "description": "node_rules CSV 文件路径"},
            "node_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选节点名称列表；为空时读取全部节点",
            },
            "biz_type": {"type": "string", "description": "可选业务类型过滤，如 register"},
        },
        "required": ["node_rules_csv"],
    }

    def execute(
        self,
        node_rules_csv: str,
        node_names: list[str] | None = None,
        biz_type: str | None = None,
    ) -> str:
        rows = filter_rows(load_csv_rows(node_rules_csv), biz_type=biz_type)
        if node_names:
            wanted = {name.strip() for name in node_names if name and name.strip()}
            rows = [row for row in rows if row.get("node_name") in wanted]
        if not rows:
            return "Error: no matching node rules found"

        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[row.get("node_name") or "unknown"].append(row)

        lines: list[str] = []
        for node_name in sorted(grouped):
            lines.append(f"节点: {node_name}")
            for row in sorted(grouped[node_name], key=_rule_priority_sort_key):
                lines.append(
                    f"- {row.get('rule_name')} | {row.get('rule_name_cn')} | "
                    f"priority={row.get('priority') or ''} | "
                    f"rule_status={row.get('rule_status') or ''} | "
                    f"strategy={row.get('strategy') or ''} | "
                    f"reason_code={row.get('reason_code') or ''}"
                )
        return "\n".join(lines)


def _rule_priority_sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    raw_priority = (row.get("priority") or "").strip()
    try:
        priority = int(raw_priority)
    except ValueError:
        priority = 10**9
    return priority, row.get("rule_name") or "", row.get("rule_name_cn") or ""


def main(node_rules_csv: str, node_names: list[str] | None = None, biz_type: str | None = None) -> int:
    output = ReadNodeTool().execute(node_rules_csv=node_rules_csv, node_names=node_names, biz_type=biz_type)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("../../demo/data/node_rules.csv", node_names=["邮箱规则节点"], biz_type="register"))
