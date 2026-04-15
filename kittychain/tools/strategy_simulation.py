"""Simulate strategy execution from CSV workflow and rule definitions."""

from __future__ import annotations

import ast
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from _internal_csv import filter_rows, load_csv_rows, parse_json_dict  # type: ignore
    from base import Tool  # type: ignore
else:
    from ._internal_csv import filter_rows, load_csv_rows, parse_json_dict
    from .base import Tool


_COMPARATORS = {
    "且": "&&",
    "或": "||",
    "visual_condition_eq": "=",
    "visual_condition_not_eq": "!=",
    "visual_condition_lt": "<",
    "visual_condition_me": ">=",
    "visual_condition_mt": ">",
    "visual_condition_in": "in",
    "visual_condition_not_in": "__not_in__",
    "visual_condition_true": "__is_true__",
    "visual_condition_false": "__is_false__",
    "visual_condition_empty": "__is_empty__",
    "visual_condition_not_empty": "__not_empty__",
    "visual_condition_startWith": "__starts_with__",
}
_TOKEN_PATTERN = re.compile(r"\s*(\|\||&&|\(|\)|!=|>=|<=|=|<|>|__not_in__|in|,|\[[^]]*\]|'[^']*'|\"[^\"]*\"|[^\s(),]+)")
_STRATEGY_PRIORITY = {"reject": 3, "review": 2, "pass": 1, "accept": 1, "": 0}


class StrategySimulationTool(Tool):
    name = "strategy_simulation"
    description = "执行策略工作流模拟，并将每个请求的命中规则、策略结果和原因码保存到 CSV。"
    parameters = {
        "type": "object",
        "properties": {
            "biz_flow_csv": {"type": "string", "description": "biz_flow CSV 文件路径"},
            "node_rules_csv": {"type": "string", "description": "node_rules CSV 文件路径"},
            "rule_details_csv": {"type": "string", "description": "rule_details CSV 文件路径"},
            "biz_variables_csv": {"type": "string", "description": "biz_variables CSV 文件路径"},
            "biz_inputs_csv": {"type": "string", "description": "biz_inputs CSV 文件路径"},
            "rule_hits_csv": {"type": "string", "description": "rule_hits CSV 文件路径"},
            "condition_md": {"type": "string", "description": "condition.md 文件路径"},
            "user_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选 user_id 列表；为空时处理全部请求",
            },
            "path": {"type": "string", "description": "结果保存路径"},
        },
        "required": [
            "biz_flow_csv",
            "node_rules_csv",
            "rule_details_csv",
            "biz_variables_csv",
            "biz_inputs_csv",
            "rule_hits_csv",
            "condition_md",
            "path",
        ],
    }

    def execute(
        self,
        biz_flow_csv: str,
        node_rules_csv: str,
        rule_details_csv: str,
        biz_variables_csv: str,
        biz_inputs_csv: str,
        rule_hits_csv: str,
        condition_md: str,
        path: str,
        user_ids: list[str] | None = None,
    ) -> str:
        if not str(path).strip():
            return "Error: path is required"

        biz_type = _detect_biz_type(rule_hits_csv)
        try:
            flow = _load_flow(biz_flow_csv, biz_type)
            conditions = _load_conditions(Path(condition_md).expanduser(), flow["has_condition_nodes"])
            node_rules = _load_node_rules(node_rules_csv, biz_type)
            rule_details = _load_rule_details(rule_details_csv, biz_type)
            input_names = _load_input_names(Path(biz_inputs_csv).expanduser())
            variable_names = _load_variable_names(biz_variables_csv, biz_type)
            hit_rows = filter_rows(load_csv_rows(rule_hits_csv), biz_type=biz_type)
            if user_ids:
                wanted = {user_id.strip() for user_id in user_ids if user_id and user_id.strip()}
                hit_rows = [row for row in hit_rows if row.get("user_id") in wanted]

            results = [
                _simulate_row(row, flow, conditions, node_rules, rule_details, input_names, variable_names)
                for row in hit_rows
            ]
            _write_results(path, results)
        except Exception as exc:
            return f"Error: {exc}"

        return f"Results have been saved to {path}"


def _detect_biz_type(rule_hits_csv: str) -> str | None:
    rows = load_csv_rows(rule_hits_csv)
    if not rows:
        return None
    return rows[0].get("biz_type") or None


def _load_flow(biz_flow_csv: str, biz_type: str | None) -> dict[str, object]:
    rows = filter_rows(load_csv_rows(biz_flow_csv), biz_type=biz_type)
    if not rows:
        raise ValueError("no matching biz flow rows found")

    payload = json.loads(rows[0].get("extend") or "{}")
    nodes = payload.get("nodes") or []
    edges = sorted(payload.get("edges") or [], key=lambda item: item.get("index", 0))
    node_map = {node.get("id"): node for node in nodes if node.get("id")}
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: set[str] = set()
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in node_map and target in node_map:
            outgoing[source].append(target)
            incoming.add(target)
    roots = sorted(
        [node_id for node_id in node_map if node_id not in incoming],
        key=lambda node_id: (node_map[node_id].get("index", 0), node_map[node_id].get("label", "")),
    )
    return {
        "node_map": node_map,
        "outgoing": outgoing,
        "roots": roots,
        "has_condition_nodes": any(node.get("operatorType") == "CONDITION" for node in nodes),
    }


def _load_conditions(path: Path, required: bool) -> dict[str, str]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"{path} not found")
        return {}

    conditions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or ":" not in text:
            continue
        label, expression = text.split(":", 1)
        conditions[label.strip()] = expression.strip()
    return _load_conditions_map(conditions)


def _load_conditions_map(conditions: dict[str, str]) -> dict[str, str]:
    return {_normalize_condition_label(label): expression for label, expression in conditions.items()}


def _normalize_condition_label(label: str) -> str:
    return (label or "").strip().lower()


def _resolve_active_rule_nodes(
    flow: dict[str, object],
    conditions: dict[str, str],
    s_payload: dict[str, object],
) -> list[str]:
    node_map = flow["node_map"]
    outgoing = flow["outgoing"]
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen:
            return
        node = node_map[node_id]
        operator = node.get("operatorType")
        label = node.get("label") or ""
        if operator == "CONDITION":
            expression = conditions.get(_normalize_condition_label(label))
            if not expression:
                return
            context = {"s": s_payload, "e": {}, "raw": dict(s_payload), "names": {}}
            if not _evaluate_expression(_tokenize_expression(expression), context):
                return
        seen.add(node_id)
        if operator == "RULE":
            ordered.append(node_id)
        for child_id in outgoing.get(node_id, []):
            visit(child_id)

    for root_id in flow["roots"]:
        visit(root_id)
    return ordered


def _load_node_rules(node_rules_csv: str, biz_type: str | None) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in filter_rows(load_csv_rows(node_rules_csv), biz_type=biz_type):
        if row.get("rule_status") != "1":
            continue
        grouped[row.get("node_code") or ""].append(row)
    for key in grouped:
        grouped[key].sort(key=lambda row: (int(row.get("priority") or 0), row.get("rule_name") or ""))
    return grouped


def _load_rule_details(rule_details_csv: str, biz_type: str | None) -> dict[tuple[str, str], list[str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in filter_rows(load_csv_rows(rule_details_csv), biz_type=biz_type):
        grouped[(row.get("node_code") or "", row.get("rule_name") or "")].append(row)
    result: dict[tuple[str, str], list[str]] = {}
    for key, rows in grouped.items():
        rows.sort(key=lambda row: int(row.get("item_id") or 0))
        result[key] = [((row.get("field_cn") or "").strip() or (row.get("field") or "").strip()) for row in rows]
    return result


def _load_input_names(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(path)
    names: dict[str, str] = {}
    for row in load_csv_rows(str(path)):
        var_id = row.get("var_id") or ""
        alias = row.get("alias") or ""
        name = row.get("var_name") or var_id
        if var_id:
            names[var_id] = name
        if alias and alias != "-":
            names[alias] = name
    return names


def _load_variable_names(biz_variables_csv: str, biz_type: str | None) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in filter_rows(load_csv_rows(biz_variables_csv), biz_type=biz_type):
        var_id = row.get("var_id") or ""
        if var_id:
            names[var_id] = row.get("var_name") or var_id
    return names


def _simulate_row(
    row: dict[str, str],
    flow: dict[str, object],
    conditions: dict[str, str],
    node_rules: dict[str, list[dict[str, str]]],
    rule_details: dict[tuple[str, str], list[str]],
    input_names: dict[str, str],
    variable_names: dict[str, str],
) -> dict[str, str]:
    s_payload = parse_json_dict(row.get("s") or "")
    e_payload = parse_json_dict(row.get("e") or "")
    ordered_nodes = _resolve_active_rule_nodes(flow, conditions, s_payload)
    context = _build_context(s_payload, e_payload, input_names, variable_names)
    hits = []
    reason_codes: list[str] = []
    final_strategy = "pass"

    for node_id in ordered_nodes:
        node_code = f"node_{node_id}"
        for meta in node_rules.get(node_code, []):
            key = (node_code, meta.get("rule_name") or "")
            tokens = rule_details.get(key, [])
            hit_list, assignment_list = _split_rule_detail_tokens(tokens)
            if _contains_function_call(hit_list):
                hit = _lookup_inner_rule_result(e_payload, node_code, meta.get("rule_name") or "")
            else:
                hit = bool(_evaluate_expression(_normalize_tokens(hit_list), context))
            if not hit:
                continue
            hits.append(meta.get("rule_name") or "")
            _apply_assignments(_normalize_tokens(assignment_list), context)
            strategy = _normalize_strategy(meta.get("strategy") or "")
            if _STRATEGY_PRIORITY.get(strategy, 0) > _STRATEGY_PRIORITY.get(final_strategy, 0):
                final_strategy = strategy
            reason_code = (meta.get("reason_code") or "").strip()
            if reason_code and reason_code not in reason_codes:
                reason_codes.append(reason_code)

    return {
        "requestId": str(s_payload.get("requestId") or ""),
        "user_id": row.get("user_id") or "",
        "hit_rules": "|".join(hits),
        "strategy_result": final_strategy,
        "reason_codes": "|".join(reason_codes),
    }


def _build_context(
    s_payload: dict[str, object],
    e_payload: dict[str, object],
    input_names: dict[str, str],
    variable_names: dict[str, str],
) -> dict[str, object]:
    raw = {}
    names = {}
    for key, value in s_payload.items():
        raw[key] = value
        if key in input_names:
            names[input_names[key]] = value
    for key, value in e_payload.items():
        raw[key] = value
        if key in variable_names:
            names[variable_names[key]] = value
        elif key in input_names:
            names[input_names[key]] = value
    return {"s": s_payload, "e": e_payload, "raw": raw, "names": names}


def _normalize_tokens(tokens: list[str]) -> list[str]:
    return [_COMPARATORS.get(token, token) for token in tokens if token]


def _split_rule_detail_tokens(tokens: list[str]) -> tuple[list[str], list[str]]:
    if not tokens:
        return [], []
    depth = 0
    split_index = len(tokens)
    for index, token in enumerate(tokens):
        depth += token.count("(")
        depth -= token.count(")")
        if depth == 0 and index + 1 < len(tokens) and tokens[index + 1] == "=":
            split_index = index
            break
    return tokens[:split_index], tokens[split_index:]


def _contains_function_call(tokens: list[str]) -> bool:
    operators = {"(", ")", "&&", "||", ",", "=", "!=", "<", ">", ">=", "<=", "in", "__not_in__"}
    for index in range(len(tokens) - 1):
        token = tokens[index]
        next_token = tokens[index + 1]
        if next_token != "(":
            continue
        if token in operators:
            continue
        if token.startswith(("s.", "e.")):
            continue
        if token in {"true", "false"}:
            continue
        if token.startswith("[") or token.startswith("{") or token.startswith(("'", '"')):
            continue
        return True
    return False


def _lookup_inner_rule_result(e_payload: dict[str, object], node_code: str, rule_name: str) -> bool:
    result_map = e_payload.get("inner_rule_result") or {}
    if not isinstance(result_map, dict):
        return False
    value = result_map.get(f"{node_code}.{rule_name}")
    if value is None:
        value = result_map.get(rule_name)
    return bool(value)


def _apply_assignments(tokens: list[str], context: dict[str, object]) -> None:
    index = 0
    while index + 2 < len(tokens):
        target = tokens[index]
        if tokens[index + 1] != "=":
            break
        next_assignment = index + 3
        while next_assignment + 1 < len(tokens) and tokens[next_assignment + 1] != "=":
            next_assignment += 1
        value_tokens = tokens[index + 2 : next_assignment if next_assignment + 1 < len(tokens) else len(tokens)]
        if next_assignment + 1 >= len(tokens):
            value_tokens = tokens[index + 2 :]
        value = _evaluate_expression(value_tokens, context) if value_tokens else None
        context["raw"][target] = value
        index = index + 2 + len(value_tokens)


def _evaluate_expression(tokens: list[str], context: dict[str, object]) -> object:
    parser = _ExpressionParser(tokens, context)
    return parser.parse()


class _ExpressionParser:
    def __init__(self, tokens: list[str], context: dict[str, object]):
        self.tokens = [token for token in tokens if token]
        self.context = context
        self.index = 0

    def parse(self) -> object:
        if not self.tokens:
            return False
        return self._parse_or()

    def _parse_or(self) -> object:
        value = self._parse_and()
        while self._peek() == "||":
            self.index += 1
            value = bool(value) or bool(self._parse_and())
        return value

    def _parse_and(self) -> object:
        value = self._parse_comparison()
        while self._peek() == "&&":
            self.index += 1
            value = bool(value) and bool(self._parse_comparison())
        return value

    def _parse_comparison(self) -> object:
        value = self._parse_additive()
        operator = self._peek()
        if operator in {"=", "!=", "<", ">", ">=", "in", "__not_in__", "__starts_with__"}:
            self.index += 1
            other = self._parse_additive()
            return _compare(value, operator, other)
        if operator in {"__is_true__", "__is_false__", "__is_empty__", "__not_empty__"}:
            self.index += 1
            return _compare_unary(value, operator)
        return value

    def _parse_additive(self) -> object:
        value = self._parse_multiplicative()
        while self._peek() in {"+", "-"}:
            operator = self._peek()
            self.index += 1
            other = self._parse_multiplicative()
            value = _apply_arithmetic(value, operator, other)
        return value

    def _parse_multiplicative(self) -> object:
        value = self._parse_primary()
        while self._peek() in {"*", "/"}:
            operator = self._peek()
            self.index += 1
            other = self._parse_primary()
            value = _apply_arithmetic(value, operator, other)
        return value

    def _parse_primary(self) -> object:
        token = self._peek()
        if token is None:
            return None
        if token == "(":
            self.index += 1
            value = self._parse_or()
            if self._peek() == ")":
                self.index += 1
            return value
        self.index += 1
        return _resolve_token_value(token, self.context)

    def _peek(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]


def _compare(left: object, operator: str, right: object) -> bool:
    if operator == "=":
        if left is None or right is None:
            return False
        return left == right
    if operator == "!=":
        if left is None or right is None:
            return False
        return left != right
    if operator == "<":
        return _compare_numbers(left, right, lambda lhs, rhs: lhs < rhs)
    if operator == ">":
        return _compare_numbers(left, right, lambda lhs, rhs: lhs > rhs)
    if operator == ">=":
        return _compare_numbers(left, right, lambda lhs, rhs: lhs >= rhs)
    if operator == "in":
        return left in _coerce_collection(right)
    if operator == "__not_in__":
        return left not in _coerce_collection(right)
    if operator == "__starts_with__":
        return str(left).startswith(str(right))
    return False


def _compare_unary(value: object, operator: str) -> bool:
    if operator == "__is_true__":
        return bool(value) is True
    if operator == "__is_false__":
        return bool(value) is False
    if operator == "__is_empty__":
        return value in (None, "", [], {})
    if operator == "__not_empty__":
        return value not in (None, "", [], {})
    return False


def _coerce_number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


def _compare_numbers(left: object, right: object, predicate) -> bool:
    try:
        return predicate(_coerce_number(left), _coerce_number(right))
    except (TypeError, ValueError):
        return False


def _apply_arithmetic(left: object, operator: str, right: object) -> object:
    try:
        lhs = _coerce_number(left)
        rhs = _coerce_number(right)
    except (TypeError, ValueError):
        return None
    if operator == "+":
        return lhs + rhs
    if operator == "-":
        return lhs - rhs
    if operator == "*":
        return lhs * rhs
    if operator == "/":
        if rhs == 0:
            return None
        return lhs / rhs
    return None


def _coerce_collection(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return [value]


def _resolve_token_value(token: str, context: dict[str, object]) -> object:
    if token.startswith("s."):
        return context["s"].get(token[2:])
    if token.startswith("e."):
        return context["e"].get(token[2:])
    if token in context["raw"]:
        return context["raw"][token]
    if token in context["names"]:
        return context["names"][token]
    if token == "true":
        return True
    if token == "false":
        return False
    if token in {"null", "None"}:
        return None
    if token.startswith(("[", "{", "'", '"')) or re.fullmatch(r"-?\d+(\.\d+)?", token):
        try:
            return ast.literal_eval(token)
        except (ValueError, SyntaxError):
            return token
    return None


def _tokenize_expression(expression: str) -> list[str]:
    text = expression.replace(" not in ", " __not_in__ ")
    return [match.group(1) for match in _TOKEN_PATTERN.finditer(text) if match.group(1)]


def _normalize_strategy(value: str) -> str:
    text = value.strip().lower()
    if text in {"", "pass", "accept"}:
        return "pass"
    return text


def _write_results(path: str, rows: list[dict[str, str]]) -> None:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["requestId", "user_id", "hit_rules", "strategy_result", "reason_codes"])
        for row in rows:
            writer.writerow(
                [
                    row["requestId"],
                    row["user_id"],
                    row["hit_rules"],
                    row["strategy_result"],
                    row["reason_codes"],
                ]
            )


def main(
    biz_flow_csv: str,
    node_rules_csv: str,
    rule_details_csv: str,
    biz_variables_csv: str,
    biz_inputs_csv: str,
    rule_hits_csv: str,
    condition_md: str,
    path: str,
    user_ids: list[str] | None = None,
) -> int:
    output = StrategySimulationTool().execute(
        biz_flow_csv=biz_flow_csv,
        node_rules_csv=node_rules_csv,
        rule_details_csv=rule_details_csv,
        biz_variables_csv=biz_variables_csv,
        biz_inputs_csv=biz_inputs_csv,
        rule_hits_csv=rule_hits_csv,
        condition_md=condition_md,
        path=path,
        user_ids=user_ids,
    )
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    demo_root = Path(__file__).resolve().parents[2] / "demo" / "data"
    raise SystemExit(
        main(
            str(demo_root / "biz_flow.csv"),
            str(demo_root / "node_rules.csv"),
            str(demo_root / "rule_details.csv"),
            str(demo_root / "biz_variables.csv"),
            str(demo_root / "biz_inputs.csv"),
            str(demo_root / "rule_hits.csv"),
            str(demo_root / "condition.md"),
            str(demo_root.parent / "out.csv"),
        )
    )
