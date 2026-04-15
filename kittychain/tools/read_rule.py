"""Read rule detail CSV files into text explanations."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from _internal_csv import filter_rows, load_csv_rows, stringify_tokens  # type: ignore
else:
    from ._internal_csv import filter_rows, load_csv_rows, stringify_tokens
    from .base import Tool


_RULE_TOKEN_MAP = {
    "visual_condition_empty": "不存在",
    "visual_condition_eq": "=",
    "visual_condition_false": "为假",
    "visual_condition_in": "in",
    "visual_condition_lt": "<",
    "visual_condition_me": ">=",
    "visual_condition_mt": ">",
    "visual_condition_not_empty": "存在",
    "visual_condition_not_eq": "!=",
    "visual_condition_not_in": "not in",
    "visual_condition_startWith": "始于",
    "visual_condition_true": "为真",
}


class ReadRuleTool(Tool):
    name = "read_rule"
    description = "读取规则详情 CSV，并返回规则命中逻辑、赋值逻辑、策略结果和原因码。"
    parameters = {
        "type": "object",
        "properties": {
            "node_rules_csv": {"type": "string", "description": "node_rules CSV 文件路径"},
            "rule_details_csv": {"type": "string", "description": "rule_details CSV 文件路径"},
            "rule_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选规则英文名列表",
            },
            "rule_name_cns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选规则中文名列表",
            },
            "biz_type": {"type": "string", "description": "可选业务类型过滤，如 register"},
        },
        "required": ["node_rules_csv", "rule_details_csv"],
    }

    def execute(
        self,
        node_rules_csv: str,
        rule_details_csv: str,
        rule_names: list[str] | None = None,
        rule_name_cns: list[str] | None = None,
        biz_type: str | None = None,
    ) -> str:
        if not rule_names and not rule_name_cns:
            return "Error: rule_names or rule_name_cns is required"

        rule_rows = filter_rows(load_csv_rows(node_rules_csv), biz_type=biz_type)
        detail_rows = filter_rows(load_csv_rows(rule_details_csv), biz_type=biz_type)
        rule_name_set = {name.strip() for name in (rule_names or []) if name and name.strip()}
        rule_name_cn_set = {name.strip() for name in (rule_name_cns or []) if name and name.strip()}

        filtered_details = [
            row
            for row in detail_rows
            if row.get("rule_name") in rule_name_set or row.get("rule_name_cn") in rule_name_cn_set
        ]
        if not filtered_details:
            return "Error: no matching rule details found"

        meta_by_rule_name = {row.get("rule_name"): row for row in rule_rows if row.get("rule_name")}
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in filtered_details:
            grouped[row.get("rule_name_cn") or row.get("rule_name") or "unknown"].append(row)

        lines: list[str] = []
        for rule_name_cn in sorted(grouped):
            rows = sorted(grouped[rule_name_cn], key=lambda item: int(item.get("item_id") or 0))
            rule_name = rows[0].get("rule_name") or ""
            tokens = [_map_rule_token((row.get("field_cn") or row.get("field") or "").strip()) for row in rows]
            hit_logic, assignment_logic = _split_rule_tokens(tokens)
            meta = meta_by_rule_name.get(rule_name, {})
            lines.append(f"规则: {rule_name_cn} ({rule_name})")
            lines.append(f"命中逻辑: {hit_logic or '-'}")
            lines.append(f"赋值逻辑: {assignment_logic or '-'}")
            lines.append(f"策略结果: {meta.get('strategy') or '-'}")
            lines.append(f"原因码: {meta.get('reason_code') or '-'}")
        return "\n".join(lines)


def _split_rule_tokens(tokens: list[str]) -> tuple[str, str]:
    if not tokens:
        return "", ""
    depth = 0
    split_index = len(tokens)
    for index, token in enumerate(tokens):
        depth += token.count("(")
        depth -= token.count(")")
        if depth == 0 and index + 1 < len(tokens) and tokens[index + 1] == "=":
            split_index = index
            break
    hit_tokens = tokens[:split_index]
    assignment_tokens = tokens[split_index:]
    return stringify_tokens(hit_tokens), stringify_tokens(assignment_tokens)


def _map_rule_token(token: str) -> str:
    return _RULE_TOKEN_MAP.get(token, token)


def main(
    node_rules_csv: str,
    rule_details_csv: str,
    rule_names: list[str] | None = None,
    rule_name_cns: list[str] | None = None,
    biz_type: str | None = None,
) -> int:
    output = ReadRuleTool().execute(
        node_rules_csv=node_rules_csv,
        rule_details_csv=rule_details_csv,
        rule_names=rule_names,
        rule_name_cns=rule_name_cns,
        biz_type=biz_type,
    )
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("../../demo/data/node_rules.csv", "../../demo/data/rule_details.csv", rule_name_cns=["GPS聚集规则1H"], biz_type="register"))
