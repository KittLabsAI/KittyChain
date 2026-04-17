from __future__ import annotations

import csv
import json
from ast import literal_eval
from collections import OrderedDict
from datetime import datetime
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _schemas_root() -> Path:
    return Path(__file__).resolve().parent / "schemas"


def _data_root() -> Path:
    return _repo_root() / "demo" / "data"


def _read_csv(name: str) -> list[dict[str, str]]:
    path = _data_root() / name
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_json_column(rows: list[dict[str, str]], column: str) -> list[dict[str, object]]:
    return [json.loads(row[column]) for row in rows]


def _iso_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    return datetime.fromisoformat(value).isoformat()


def _rule_engine_timestamp() -> str:
    return "2026-04-15T00:00:00Z"


def _normalize_type(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


DATA_TYPE_MAP = {
    "1": "double",
    "2": "string",
    "3": "long",
    "4": "list",
    "5": "bool",
    "6": "map",
    "7": "other",
    "8": "other",
}


def _first_example(samples: dict[str, object], key: str) -> list[object]:
    if key not in samples:
        return []
    return [samples[key]]


def _first_default(samples: dict[str, object], key: str) -> object:
    return samples.get(key)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _condition_map() -> dict[str, str]:
    conditions: dict[str, str] = {}
    path = _data_root() / "condition.md"
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        label, expression = line.split(":", 1)
        conditions[label.strip()] = expression.strip()
    return conditions


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _add_variable_name_mapping(
    variable_name_to_key: dict[str, str],
    variable_name: str | None,
    variable_key: str,
) -> None:
    cleaned_name = _clean_text(variable_name)
    if cleaned_name:
        variable_name_to_key.setdefault(cleaned_name, variable_key)


def _map_rule_variable_arg(value: object, variable_name_to_key: dict[str, str]) -> object:
    if isinstance(value, str):
        return variable_name_to_key.get(value, value)
    return _map_rule_variable_refs(value, variable_name_to_key)


def _map_rule_variable_refs(value: object, variable_name_to_key: dict[str, str]) -> object:
    if isinstance(value, list):
        return [_map_rule_variable_refs(item, variable_name_to_key) for item in value]
    if not isinstance(value, dict):
        return value

    mapped: dict[str, object] = {}
    for key, item in value.items():
        if key == "var" and isinstance(item, str):
            mapped[key] = variable_name_to_key.get(item, item)
        elif key == "right_var" and isinstance(item, str):
            mapped[key] = variable_name_to_key.get(item, item)
        elif key == "value" and isinstance(item, str):
            mapped_value = variable_name_to_key.get(item, item)
            if mapped_value in variable_name_to_key.values():
                mapped["right_var"] = mapped_value
            else:
                mapped[key] = mapped_value
        elif key == "args" and isinstance(item, list):
            mapped[key] = [_map_rule_variable_arg(arg, variable_name_to_key) for arg in item]
        else:
            mapped[key] = _map_rule_variable_refs(item, variable_name_to_key)
    return mapped


EXPRESSION_OPERATOR_MAP = {
    "visual_condition_empty": "not exist",
    "visual_condition_eq": "=",
    "visual_condition_false": "is false",
    "visual_condition_in": "in",
    "visual_condition_lt": "<",
    "visual_condition_me": ">=",
    "visual_condition_mt": ">",
    "visual_condition_not_empty": "exist",
    "visual_condition_not_eq": "!=",
    "visual_condition_not_in": "not in",
    "visual_condition_startWith": "start with",
    "visual_condition_true": "is true",
    "&&": "and",
    "||": "or",
    "且": "and",
    "或": "or",
}

COMPARISON_OPERATORS = {
    "=",
    "!=",
    ">",
    ">=",
    "<",
    "in",
    "not in",
    "start with",
    "exist",
    "not exist",
    "is true",
    "is false",
}

UNARY_OPERATORS = {"exist", "not exist", "is true", "is false"}
BOOLEAN_OPERATORS = {"and", "or"}
ARITHMETIC_OPERATORS = {"+", "-", "*", "/"}


def _strip_source_trace_fields(value: object) -> object:
    forbidden_keys = {"source_file", "source_row_id", "source_system", "mapping_method", "raw_fragments"}
    if isinstance(value, dict):
        return {
            key: _strip_source_trace_fields(item)
            for key, item in value.items()
            if key not in forbidden_keys
        }
    if isinstance(value, list):
        return [_strip_source_trace_fields(item) for item in value]
    return value


def _sanitize_schema_json_files(root: Path) -> None:
    for path in root.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _write_json(path, _strip_source_trace_fields(payload))


def _rule_detail_key(row: dict[str, str]) -> str:
    return _clean_text(row["rule_name_cn"]) or row["rule_name"]


def _rule_detail_token(row: dict[str, str]) -> str:
    token = _clean_text(row["field_cn"]) or row["field"]
    return EXPRESSION_OPERATOR_MAP.get(token, token)


def _format_expression_tokens(tokens: list[str]) -> str:
    if not tokens:
        return ""
    formatted = " ".join(token for token in tokens if token)
    formatted = formatted.replace("( ", "(")
    formatted = formatted.replace(" )", ")")
    formatted = formatted.replace(" ,", ",")
    return formatted.strip()


def _split_rule_expressions(detail_rows: list[dict[str, str]]) -> tuple[str, str]:
    tokens = [_rule_detail_token(row) for row in detail_rows]
    split_index: int | None = None
    depth = 0
    for index, token in enumerate(tokens[:-1]):
        if token == "(":
            depth += 1
            continue
        if token == ")":
            depth = max(depth - 1, 0)
            continue
        if depth == 0 and tokens[index + 1] == "=":
            split_index = index
            break
    if split_index is None:
        return _format_expression_tokens(tokens), ""
    return (
        _format_expression_tokens(tokens[:split_index]),
        _format_expression_tokens(tokens[split_index:]),
    )


def _normalize_assignment_tokens(tokens: list[str]) -> list[str]:
    normalized = []
    for token in tokens:
        if token == "set":
            continue
        normalized.append(token)
    return normalized


def _parse_scalar_token(token: str) -> object:
    if token == "true":
        return True
    if token == "false":
        return False
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    if token.startswith("[") and token.endswith("]"):
        return literal_eval(token)
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        return token


def _find_matching_paren(tokens: list[str], start: int) -> int:
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index] == "(":
            depth += 1
        elif tokens[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Unmatched parenthesis in expression tokens.")


def _strip_wrapping_parens(tokens: list[str]) -> list[str]:
    current = tokens
    while len(current) >= 2 and current[0] == "(" and current[-1] == ")":
        end = _find_matching_paren(current, 0)
        if end != len(current) - 1:
            break
        current = current[1:-1]
    return current


def _split_top_level_binary(tokens: list[str], operator: str) -> tuple[list[str], list[str]] | None:
    depth = 0
    for index in range(len(tokens) - 1, -1, -1):
        token = tokens[index]
        if token == "(":
            depth -= 1
        elif token == ")":
            depth += 1
        elif depth == 0 and token == operator:
            return tokens[:index], tokens[index + 1 :]
    return None


def _split_top_level_binary_any(tokens: list[str], operators: tuple[str, ...]) -> tuple[list[str], str, list[str]] | None:
    depth = 0
    for index in range(len(tokens) - 1, -1, -1):
        token = tokens[index]
        if token == "(":
            depth -= 1
        elif token == ")":
            depth += 1
        elif depth == 0 and token in operators:
            return tokens[:index], token, tokens[index + 1 :]
    return None


def _parse_operand_tokens(tokens: list[str]) -> object:
    current = _strip_wrapping_parens(tokens)
    if not current:
        return ""
    split = _split_top_level_binary_any(current, ("+", "-"))
    if split is not None:
        left, operator, right = split
        return _build_binary_operand(left, operator, right)
    split = _split_top_level_binary_any(current, ("*", "/"))
    if split is not None:
        left, operator, right = split
        return _build_binary_operand(left, operator, right)
    if len(current) == 1:
        return _parse_scalar_token(current[0])
    if len(current) > 1 and current[1] == "(" and current[-1] == ")":
        end = _find_matching_paren(current, 1)
        if end == len(current) - 1:
            args = _parse_function_args(current[2:-1])
            return {
                "function": current[0],
                "args": args,
            }
    return " ".join(current)


def _build_binary_operand(left_tokens: list[str], operator: str, right_tokens: list[str]) -> dict[str, object]:
    left = _parse_operand_tokens(left_tokens)
    right = _parse_operand_tokens(right_tokens)
    return {
        "var": left,
        "operator": operator,
        "value": right,
    }


def _parse_function_args(tokens: list[str]) -> list[object]:
    if not tokens:
        return []
    args: list[object] = []
    start = 0
    depth = 0
    for index, token in enumerate(tokens):
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif token == "," and depth == 0:
            args.append(_parse_operand_tokens(tokens[start:index]))
            start = index + 1
    args.append(_parse_operand_tokens(tokens[start:]))
    return args


def _parse_atomic_expression(tokens: list[str]) -> object:
    current = _strip_wrapping_parens(tokens)
    depth = 0
    for index, token in enumerate(current):
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0 and token in COMPARISON_OPERATORS:
            left = _parse_operand_tokens(current[:index])
            if token in UNARY_OPERATORS:
                return {
                    "var": left,
                    "operator": token,
                }
            right = _parse_operand_tokens(current[index + 1 :])
            return {
                "var": left,
                "operator": token,
                "value": right,
            }
    parsed = _parse_operand_tokens(current)
    if isinstance(parsed, str):
        return {
            "var": parsed,
            "operator": "is true",
        }
    return parsed


def _parse_hit_expression(tokens: list[str]) -> object:
    current = _strip_wrapping_parens(tokens)
    for operator in ("and", "or"):
        split = _split_top_level_binary(current, operator)
        if split is not None:
            left, right = split
            return {
                operator: [
                    _parse_hit_expression(left),
                    _parse_hit_expression(right),
                ]
            }
    return _parse_atomic_expression(current)


def _parse_assignment_expression(tokens: list[str]) -> list[dict[str, object]]:
    current = _normalize_assignment_tokens(tokens)
    assignments: list[dict[str, object]] = []
    index = 0
    while index < len(current):
        var_name = current[index]
        if index + 1 >= len(current) or current[index + 1] != "=":
            raise ValueError(f"Invalid assignment expression near token {var_name!r}.")
        value_start = index + 2
        value_end = value_start
        depth = 0
        while value_end < len(current):
            token = current[value_end]
            if token == "(":
                depth += 1
            elif token == ")":
                depth -= 1
            next_is_assignment = (
                depth == 0
                and value_end + 2 < len(current)
                and current[value_end + 1] not in BOOLEAN_OPERATORS
                and current[value_end + 2] == "="
            )
            if next_is_assignment:
                break
            value_end += 1
        value_tokens = current[value_start:value_end + 1]
        assignments.append(
            {
                "var": var_name,
                "operator": "set",
                "value": _parse_operand_tokens(value_tokens),
            }
        )
        index = value_end + 1
    return assignments


def _build_rule_expressions(detail_rows: list[dict[str, str]]) -> tuple[object, list[dict[str, object]]]:
    tokens = [_rule_detail_token(row) for row in detail_rows]
    split_index: int | None = None
    depth = 0
    for index, token in enumerate(tokens[:-1]):
        if token == "(":
            depth += 1
            continue
        if token == ")":
            depth = max(depth - 1, 0)
            continue
        if depth == 0 and tokens[index + 1] == "=":
            split_index = index
            break
    if split_index is None:
        return _parse_hit_expression(tokens), []
    return (
        _parse_hit_expression(tokens[:split_index]),
        _parse_assignment_expression(tokens[split_index:]),
    )


def generate_register_scene() -> None:
    schemas_root = _schemas_root()
    demo_scene_root = schemas_root / "scenes" / "demo"
    register_scene_root = schemas_root / "scenes" / "register"

    risk_scenes = json.loads((schemas_root / "risk_scenes.json").read_text(encoding="utf-8"))
    public_variables = json.loads((schemas_root / "public_variables.json").read_text(encoding="utf-8"))
    history_data = json.loads((schemas_root / "history_data.json").read_text(encoding="utf-8"))
    user_labels = json.loads((schemas_root / "user_labels.json").read_text(encoding="utf-8"))
    variable_rows = _read_csv("biz_variables.csv")
    history_data["records"] = [
        record for record in history_data["records"] if record["scene_key"] != "register"
    ]
    common_variable_rows: OrderedDict[str, dict[str, str]] = OrderedDict()
    for row in variable_rows:
        if row["biz_type"] == "common":
            common_variable_rows.setdefault(row["var_id"], row)
    public_variables["variables"] = [
        variable
        for variable in public_variables["variables"]
        if variable["variable_key"] not in common_variable_rows
    ]
    user_labels["labels"] = [
        label for label in user_labels["labels"] if label.get("scene_key") != "register"
    ]

    flow_row = _read_csv("biz_flow.csv")[0]
    flow_graph = json.loads(flow_row["extend"])
    node_rule_rows = [row for row in _read_csv("node_rules.csv") if row["biz_type"] == "register"]
    rule_detail_rows = [row for row in _read_csv("rule_details.csv") if row["biz_type"] == "register"]
    rule_hit_rows = [row for row in _read_csv("rule_hits.csv") if row["biz_type"] == "register"]
    label_rows = _read_csv("user_labels.csv")
    input_rows = _read_csv("biz_inputs.csv")
    variable_name_to_key: dict[str, str] = {}
    for row in input_rows:
        _add_variable_name_mapping(variable_name_to_key, row["var_name"], row["var_id"])
    for row in variable_rows:
        if row["biz_type"] not in {"register", "common"}:
            continue
        _add_variable_name_mapping(variable_name_to_key, row["var_name"], row["var_id"])

    condition_map = _condition_map()
    source_inputs = _read_json_column(rule_hit_rows, "s")
    source_derived = _read_json_column(rule_hit_rows, "e")

    input_samples: dict[str, object] = {}
    for payload in source_inputs:
        for key, value in payload.items():
            input_samples.setdefault(key, value)

    derived_samples: dict[str, object] = {}
    for payload in source_derived:
        for key, value in payload.items():
            derived_samples.setdefault(key, value)

    owners: list[str] = []
    for node in flow_graph["nodes"]:
        for owner in (node.get("nodeInfo") or {}).get("owners", []):
            if owner not in owners:
                owners.append(owner)

    scene_entry = {
        "scene_key": "register",
        "scene_name": flow_row["biz_name"],
        "description": flow_row["biz_name"],
        "status": "active",
        "scene_path": "schemas/scenes/register",
        "entry_workflow_id": "workflow_register_main",
        "owners": owners,
        "tags": ["register"],
        "created_at": flow_row["dt"],
        "updated_at": flow_row["dt"],
    }
    risk_scenes["generated_at"] = _rule_engine_timestamp()
    risk_scenes["scenes"] = [scene for scene in risk_scenes["scenes"] if scene["scene_key"] != "register"] + [scene_entry]

    workflow_nodes: list[dict[str, object]] = []
    workflow_node_lookup: dict[str, dict[str, object]] = {}
    type_map = {
        "INIT": "init",
        "RULE": "rule",
        "CONDITION": "condition",
        "COLLECT": "collect",
    }
    for node in flow_graph["nodes"]:
        node_id = f"node_{node['id']}"
        workflow_node = {
            "node_id": node_id,
            "node_type": type_map.get(node.get("operatorType"), "custom"),
            "label": node["label"],
            "enabled": True,
            "position": {
                "x": float(node.get("x", 0.0)),
                "y": float(node.get("y", 0.0)),
            },
        }
        workflow_nodes.append(workflow_node)
        workflow_node_lookup[node_id] = node

    workflow_edges = []
    for edge in sorted(flow_graph["edges"], key=lambda item: item["index"]):
        source_node_id = f"node_{edge['source']}"
        source_label = workflow_node_lookup[source_node_id]["label"]
        workflow_edges.append(
            {
                "edge_id": f"edge_{edge['id']}",
                "source_node_id": source_node_id,
                "target_node_id": f"node_{edge['target']}",
                "order": int(edge["index"]) + 1,
                "condition_ref": condition_map.get(source_label),
            }
        )

    _write_json(
        register_scene_root / "workflow.json",
        {
            "scene_key": "register",
            "workflow_id": "workflow_register_main",
            "workflow_name": flow_row["biz_name"],
            "entry_node_ids": [
                workflow_node["node_id"]
                for workflow_node in workflow_nodes
                if workflow_node["node_type"] == "init"
            ],
            "nodes": workflow_nodes,
            "edges": workflow_edges,
            "metadata": {},
        },
    )

    detail_by_rule: dict[str, list[dict[str, str]]] = OrderedDict()
    for row in rule_detail_rows:
        detail_by_rule.setdefault(_rule_detail_key(row), []).append(row)
    for rows in detail_by_rule.values():
        rows.sort(key=lambda item: int(item["item_id"]))

    edges_by_source: dict[str, list[str]] = {}
    for edge in workflow_edges:
        edges_by_source.setdefault(edge["source_node_id"], []).append(edge["target_node_id"])

    node_groups: dict[str, list[dict[str, str]]] = OrderedDict()
    for row in node_rule_rows:
        node_groups.setdefault(row["node_code"], []).append(row)

    scene_nodes = []
    rules = []
    for node_code, rows in node_groups.items():
        rows.sort(key=lambda item: int(item["priority"]))
        flow_node = workflow_node_lookup[node_code]
        scene_nodes.append(
            {
                "node_id": node_code,
                "node_name": rows[0]["node_name"],
                "node_type": type_map.get(flow_node.get("operatorType"), "custom"),
                "description": _clean_text((flow_node.get("nodeInfo") or {}).get("description")),
                "rule_refs": [
                    {
                        "rule_id": row["rule_name"],
                        "priority": int(row["priority"]) if row["priority"] else None,
                        "enabled": row["rule_status"] == "1",
                    }
                    for row in rows
                ],
                "next_node_ids": edges_by_source.get(node_code, []),
                "metadata": {
                    "owners": (flow_node.get("nodeInfo") or {}).get("owners", []),
                    "source_node_statuses": sorted({row["node_status"] for row in rows}),
                },
            }
        )

        for row in rows:
            fragments = detail_by_rule[_rule_detail_key(row)]
            hit_expression, assignment_expression = _build_rule_expressions(fragments)
            hit_expression = _map_rule_variable_refs(hit_expression, variable_name_to_key)
            assignment_expression = _map_rule_variable_refs(assignment_expression, variable_name_to_key)
            reason_codes = [row["reason_code"]] if row["reason_code"] else []
            if row["strategy"]:
                action = row["strategy"]
            else:
                action = "accept"
            rules.append(
                {
                    "rule_id": row["rule_name"],
                    "rule_name": row["rule_name"],
                    "rule_name_cn": _clean_text(row["rule_name_cn"]),
                    "status": "active" if row["rule_status"] == "1" else "inactive",
                    "priority": int(row["priority"]) if row["priority"] else None,
                    "hit_expression": hit_expression,
                    "assignment_expression": assignment_expression,
                    "action": action,
                    "reason_codes": reason_codes,
                    "metadata": {
                        "source_node_status": row["node_status"],
                    },
                }
            )

    _write_json(
        register_scene_root / "nodes.json",
        {
            "scene_key": "register",
            "nodes": scene_nodes,
        },
    )
    _write_json(
        register_scene_root / "rules.json",
        {
            "scene_key": "register",
            "rules": rules,
        },
    )

    input_ids = {row["var_id"] for row in input_rows}
    register_variables = []
    for row in input_rows:
        source_key = row["alias"] if row["alias"] and row["alias"] != "-" else row["var_id"]
        sample = input_samples.get(source_key)
        register_variables.append(
            {
                "variable_key": row["var_id"],
                "variable_name": row["var_name"],
                "scope": "input",
                "data_type": _normalize_type(sample),
                "description": row["var_name"],
                "source_path": f"s.{source_key}",
                "default_value": sample,
                "examples": _first_example(input_samples, source_key),
                "searchable": True,
                "metadata": {
                    "alias": None if row["alias"] == "-" else row["alias"],
                },
            }
        )

    for row in variable_rows:
        if row["biz_type"] != "register" or row["var_id"] in input_ids:
            continue
        sample = derived_samples.get(row["var_id"])
        register_variables.append(
            {
                "variable_key": row["var_id"],
                "variable_name": row["var_name"],
                "scope": "derived",
                "data_type": DATA_TYPE_MAP[row["data_type"]],
                "description": row["var_name"],
                "source_path": f"e.{row['var_id']}",
                "default_value": sample,
                "examples": _first_example(derived_samples, row["var_id"]),
                "searchable": True,
                "metadata": {},
            }
        )

    _write_json(
        register_scene_root / "variables.json",
        {
            "scene_key": "register",
            "variables": register_variables,
        },
    )

    existing_public_keys = {variable["variable_key"] for variable in public_variables["variables"]}
    for row in common_variable_rows.values():
        sample = derived_samples.get(row["var_id"])
        public_variables["variables"].append(
            {
                "variable_key": row["var_id"],
                "variable_name": row["var_name"],
                "scope": "public",
                "data_type": DATA_TYPE_MAP[row["data_type"]],
                "description": row["var_name"],
                "source_path": f"shared.{row['var_id']}",
                "default_value": sample,
                "examples": _first_example(derived_samples, row["var_id"]),
                "searchable": True,
                "shared_by": ["register"],
                "metadata": {},
            }
        )
    _write_json(schemas_root / "public_variables.json", public_variables)

    known_rule_ids = {rule["rule_id"] for rule in rules}
    for index, row in enumerate(rule_hit_rows, start=1):
        source_input = json.loads(row["s"])
        source_derived = json.loads(row["e"])
        source_output = json.loads(row["o"])
        hit_rules = []
        for rule_path, hit in (source_derived.get("inner_rule_result") or {}).items():
            if not hit:
                continue
            _, rule_id = rule_path.split(".", 1)
            if rule_id in known_rule_ids:
                hit_rules.append(rule_id)
        reason_codes = ((source_output.get("data") or {}).get("reasonCode")) or []
        strategy = (source_output.get("strategy") or [None])[0]
        request_id = source_input.get("requestId") or f"row_{index:04d}"
        history_data["records"].append(
            {
                "record_id": f"history_register_{request_id}",
                "scene_key": "register",
                "user_id": row["user_id"] or source_input.get("regUserId") or source_input.get("userId"),
                "event_time": _iso_timestamp(row["f_timestamp"]),
                "inputs": source_input,
                "derived_variables": source_derived,
                "hit_rules": hit_rules,
                "strategy_result": strategy,
                "reason_codes": reason_codes,
                "raw_refs": {
                    "decision_hit": source_output.get("hit"),
                    "request_id": request_id,
                },
            }
        )
    _write_json(schemas_root / "history_data.json", history_data)

    for row in label_rows:
        user_labels["labels"].append(
            {
                "user_id": row["user_id"],
                "label": row["label"],
                "label_type": None,
                "scene_key": "register",
                "applied_at": row["dt"],
                "metadata": {},
            }
        )
    _write_json(schemas_root / "user_labels.json", user_labels)
    _write_json(schemas_root / "risk_scenes.json", risk_scenes)

    # Keep the existing demo scene untouched while ensuring the target directory exists.
    demo_scene_root.mkdir(parents=True, exist_ok=True)
    _sanitize_schema_json_files(schemas_root)


def main() -> int:
    generate_register_scene()
    print("Generated register rule engine package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
