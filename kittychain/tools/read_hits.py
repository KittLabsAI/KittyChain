"""Read rule hit CSV files and summarize each user's key information."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(REPO_ROOT))
    from kittychain.tools.base import Tool  # type: ignore
    from kittychain.tools._internal_csv import filter_rows, load_csv_rows, parse_json_dict  # type: ignore
    from kittychain.config import Config  # type: ignore
    from kittychain.llm.provider import LLM  # type: ignore
    from kittychain.llm.provider import _strip_think_blocks  # type: ignore
else:
    from ._internal_csv import filter_rows, load_csv_rows, parse_json_dict
    from .base import Tool
    from ..config import Config
    from ..llm.provider import LLM
    from ..llm.provider import _strip_think_blocks


class ReadHitsTool(Tool):
    name = "read_hits"
    description = "读取规则命中 CSV，按用户汇总关键信息、命中规则、策略结果和原因码。"
    parameters = {
        "type": "object",
        "properties": {
            "rule_hits_csv": {"type": "string", "description": "rule_hits CSV 文件路径"},
            "biz_variables_csv": {"type": "string", "description": "biz_variables CSV 文件路径"},
            "biz_inputs_csv": {"type": "string", "description": "biz_inputs CSV 文件路径"},
            "user_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "必填用户 ID 列表, 列表不能为空",
            },
            "biz_type": {"type": "string", "description": "可选业务类型过滤，如 register"},
        },
        "required": ["rule_hits_csv", "biz_variables_csv", "biz_inputs_csv", "user_ids"],
    }

    def execute(
        self,
        rule_hits_csv: str,
        biz_variables_csv: str,
        biz_inputs_csv: str,
        user_ids: list[str] | None,
        biz_type: str | None = None,
    ) -> str:
        if user_ids is None:
            return "Error: user_ids is required"
        normalized_user_ids = [user_id.strip() for user_id in user_ids if user_id and user_id.strip()]
        if not normalized_user_ids:
            return "Error: validation failed - user_ids cannot be empty, please try again with valid user IDs. You can use `bash` tool to extract user IDs from the CSV file if needed."

        hit_rows = filter_rows(load_csv_rows(rule_hits_csv), biz_type=biz_type)
        variable_names = _load_variable_names(biz_variables_csv, biz_type)
        input_names = _load_input_names(biz_inputs_csv)
        wanted = set(normalized_user_ids)
        selected = [row for row in hit_rows if row.get("user_id") in wanted]
        if not selected:
            return "Error: no matching user hits found, please check the user IDs and try again."

        summaries = [_build_user_summary(row, input_names, variable_names) for row in selected]
        llm = _resolve_llm(getattr(self, "_parent_agent", None))
        if llm is None or not hasattr(llm, "complete"):
            return json.dumps(_build_result_payload(summaries), ensure_ascii=False)

        worker = llm.clone() if hasattr(llm, "clone") else llm
        messages = [
            {
                "role": "user",
                "content": "\n\n".join(_build_llm_block(summary) for summary in summaries),
            }
        ]
        system = (
            "你需要根据每个用户的完整信息，提炼关键信息。"
            "务必返回 json 格式的数组，格式为"
            "[{'user_id': 'xxx', 'key_information': 'xxx'}, ...]。"
            "每个用户必须且只能返回一条，不要输出额外解释。"
        )
        while True:
            response = worker.complete(messages, system=system)
            content = _strip_think_blocks((response.content or "").strip())
            print(f"LLM response:\n{content}\n---")
            try:
                llm_result = _parse_llm_result(content)
                return json.dumps(_merge_llm_result(summaries, llm_result), ensure_ascii=False)
            except ValueError as exc:
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "上一次返回解析失败，请严格按要求只返回 json 数组。"
                            f"error: {exc}"
                        ),
                    }
                )


def _build_user_summary(
    row: dict[str, str],
    input_names: dict[str, str],
    variable_names: dict[str, str],
) -> dict[str, object]:
    user_id = row.get("user_id") or ""
    s_payload = parse_json_dict(row.get("s") or "")
    e_payload = parse_json_dict(row.get("e") or "")
    o_payload = parse_json_dict(row.get("o") or "")

    hit_rules = []
    for rule_name, hit in (e_payload.get("inner_rule_result") or {}).items():
        if hit:
            hit_rules.append(str(rule_name))
    strategy_map = e_payload.get("inner_strategyMap") or {}
    reason_code_map = e_payload.get("inner_reasonCodeMap") or {}
    key_parts = []
    key_parts.extend(_map_payload_items(s_payload, input_names))
    key_parts.extend(_map_payload_items(e_payload, input_names, variable_names))

    strategy_values = list(o_payload.get("strategy") or [])
    strategy_text = ",".join(str(item) for item in strategy_values if item)
    if not strategy_text and hit_rules:
        strategy_text = ",".join(str(strategy_map.get(rule_name, "")) for rule_name in hit_rules if strategy_map.get(rule_name))
    reason_text = ",".join(str(reason_code_map.get(rule_name, "")) for rule_name in hit_rules if reason_code_map.get(rule_name))

    return {
        "user_id": user_id,
        "key_information": "; ".join(key_parts),
        "hit_rules": hit_rules,
        "strategy": strategy_text or "-",
        "reason_codes": reason_text or "-",
    }


def _build_llm_block(summary: dict[str, object]) -> str:
    return (
        f"user_id: {summary['user_id']}\n"
        f"完整信息: {summary['key_information']}\n"
    )


def _map_payload_items(
    payload: dict[str, object],
    primary_names: dict[str, str],
    fallback_names: dict[str, str] | None = None,
) -> list[str]:
    mapped = []
    for key, value in payload.items():
        if key.startswith("inner_"):
            continue
        name = primary_names.get(key)
        if name is None and fallback_names is not None:
            name = fallback_names.get(key)
        if name is None:
            continue
        mapped.append(f"{name}={value}")
    return mapped


def _load_input_names(biz_inputs_csv: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in load_csv_rows(biz_inputs_csv):
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


def _resolve_llm(agent) -> object | None:
    llm = getattr(agent, "llm", None)
    if llm is not None and hasattr(llm, "complete"):
        return llm
    try:
        config = Config.from_file()
    except Exception:
        return None
    if not getattr(config, "api_key", None) or not getattr(config, "model", None):
        return None
    return LLM(
        model=config.model,
        api_key=config.api_key,
        interface=config.interface,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def _parse_llm_result(content: str) -> list[dict[str, str]]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("result is not a list")
    result: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("result item is not an object")
        user_id = item.get("user_id")
        key_information = item.get("key_information")
        if not isinstance(user_id, str) or not isinstance(key_information, str):
            raise ValueError("result item must contain string user_id and key_information")
        result.append({"user_id": user_id, "key_information": key_information})
    return result


def _merge_llm_result(
    summaries: list[dict[str, object]],
    llm_result: list[dict[str, str]],
) -> list[dict[str, str]]:
    llm_map = {item["user_id"]: item["key_information"] for item in llm_result}
    if len(llm_map) != len(summaries):
        raise ValueError("llm result count does not match summaries")
    merged = []
    for summary in summaries:
        user_id = str(summary["user_id"])
        if user_id not in llm_map:
            raise ValueError(f"missing user_id: {user_id}")
        merged.append(
            {
                "user_id": user_id,
                "key_information": llm_map[user_id],
                "hit_rules": ",".join(summary["hit_rules"]) or "-",
                "strategy": str(summary["strategy"]),
                "reason_codes": str(summary["reason_codes"]),
            }
        )
    return merged


def _build_result_payload(summaries: list[dict[str, object]]) -> list[dict[str, str]]:
    return [
        {
            "user_id": str(summary["user_id"]),
            "key_information": str(summary["key_information"]),
            "hit_rules": ",".join(summary["hit_rules"]) or "-",
            "strategy": str(summary["strategy"]),
            "reason_codes": str(summary["reason_codes"]),
        }
        for summary in summaries
    ]


def main(
    rule_hits_csv: str,
    biz_variables_csv: str,
    biz_inputs_csv: str,
    user_ids: list[str],
    biz_type: str | None = None,
) -> int:
    output = ReadHitsTool().execute(
        rule_hits_csv=rule_hits_csv,
        biz_variables_csv=biz_variables_csv,
        biz_inputs_csv=biz_inputs_csv,
        user_ids=user_ids,
        biz_type=biz_type,
    )
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    demo_root = REPO_ROOT / "demo" / "data"
    raise SystemExit(
        main(
            str(demo_root / "rule_hits.csv"),
            str(demo_root / "biz_variables.csv"),
            str(demo_root / "biz_inputs.csv"),
            ["69a31ddbfedd740001d8da07", "69a411bf03e8250001d4c018"],
        )
    )
