from __future__ import annotations

import argparse
from ast import literal_eval

if __package__ in (None, ""):
    from diff import diff_replay_result, summarize_replay_results
    from evaluator import apply_assignments, evaluate_expression
    from loader import load_rule_engine_package
    from models import HistoryRecord, ReplayIssue, ReplayResult, RuleEnginePackage
    from query import filter_history
else:
    from .diff import diff_replay_result, summarize_replay_results
    from .evaluator import apply_assignments, evaluate_expression
    from .loader import load_rule_engine_package
    from .models import HistoryRecord, ReplayIssue, ReplayResult, RuleEnginePackage
    from .query import filter_history


def _build_runtime_context(record: HistoryRecord, package: RuleEnginePackage) -> dict[str, object]:
    context = dict(record.inputs)
    context.update(record.derived_variables)
    return context


def _expression_contains_function(expression: object) -> bool:
    if isinstance(expression, dict):
        if "function" in expression:
            return True
        return any(_expression_contains_function(value) for value in expression.values())
    if isinstance(expression, list):
        return any(_expression_contains_function(item) for item in expression)
    return False


def _build_rule_node_map(scene_package) -> dict[str, str]:
    rule_node_map: dict[str, str] = {}
    for node in scene_package.nodes:
        for rule_ref in node.rule_refs:
            rule_node_map.setdefault(rule_ref.rule_id, node.node_id)
    return rule_node_map


def _enabled_rules_in_order(scene_package) -> tuple[object, ...]:
    rules_by_id = {rule.rule_id: rule for rule in scene_package.rules}
    enabled_rules: list[object] = []
    for node in scene_package.nodes:
        for rule_ref in sorted(
            node.rule_refs,
            key=lambda item: (item.priority is None, item.priority if item.priority is not None else 0),
        ):
            if not rule_ref.enabled:
                continue
            rule = rules_by_id.get(rule_ref.rule_id)
            if rule is not None:
                enabled_rules.append(rule)
    return tuple(enabled_rules)


def _parse_workflow_condition_value(value: str) -> object:
    try:
        return literal_eval(value)
    except (ValueError, SyntaxError):
        if value.startswith(("s.", "e.")):
            return value[2:]
        return value


def _evaluate_workflow_condition(condition_ref: str | None, context: dict[str, object]) -> bool:
    if not condition_ref:
        return True

    condition = condition_ref.strip()
    for operator in (" not in ", " in ", " != ", " == "):
        if operator not in condition:
            continue
        left_token, right_token = condition.split(operator, 1)
        left_key = _parse_workflow_condition_value(left_token.strip())
        right_value = _parse_workflow_condition_value(right_token.strip())
        left_value = context.get(left_key, left_key)
        if operator == " in ":
            return left_value in right_value
        if operator == " not in ":
            return left_value not in right_value
        if operator == " == ":
            return left_value == right_value
        return left_value != right_value
    raise ValueError(f"Unsupported workflow condition: {condition_ref}")


def _active_workflow_node_ids(record: HistoryRecord, package: RuleEnginePackage) -> tuple[str, ...]:
    scene_package = package.scene_packages[record.scene_key]
    workflow = scene_package.workflow
    context = _build_runtime_context(record, package)
    workflow_nodes = {node.node_id: node for node in workflow.nodes}
    outgoing_edges: dict[str, list[object]] = {}
    for edge in workflow.edges:
        outgoing_edges.setdefault(edge.source_node_id, []).append(edge)
    for edges in outgoing_edges.values():
        edges.sort(key=lambda item: (item.order is None, item.order if item.order is not None else 0))

    active_node_ids: list[str] = []
    queue = list(workflow.entry_node_ids)
    visited: set[str] = set()
    while queue:
        node_id = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        workflow_node = workflow_nodes.get(node_id)
        if workflow_node is not None and not workflow_node.enabled:
            continue
        active_node_ids.append(node_id)
        for edge in outgoing_edges.get(node_id, []):
            if _evaluate_workflow_condition(edge.condition_ref, context):
                queue.append(edge.target_node_id)
    return tuple(active_node_ids)


def _enabled_active_rules_in_order(record: HistoryRecord, package: RuleEnginePackage) -> tuple[object, ...]:
    scene_package = package.scene_packages[record.scene_key]
    rules_by_id = {rule.rule_id: rule for rule in scene_package.rules}
    scene_nodes = {node.node_id: node for node in scene_package.nodes}
    active_node_ids = _active_workflow_node_ids(record, package)

    enabled_rules: list[object] = []
    for node_id in active_node_ids:
        scene_node = scene_nodes.get(node_id)
        if scene_node is None:
            continue
        for rule_ref in sorted(
            scene_node.rule_refs,
            key=lambda item: (item.priority is None, item.priority if item.priority is not None else 0),
        ):
            if not rule_ref.enabled:
                continue
            rule = rules_by_id.get(rule_ref.rule_id)
            if rule is not None:
                enabled_rules.append(rule)
    return tuple(enabled_rules)


def _match_rule_from_history(record: HistoryRecord, node_id: str, rule_id: str) -> bool:
    inner_rule_result = record.derived_variables.get("inner_rule_result")
    if not isinstance(inner_rule_result, dict):
        return False
    return bool(inner_rule_result.get(f"{node_id}.{rule_id}", False))


def _dedupe_preserve_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def replay_record(record: HistoryRecord, package: RuleEnginePackage) -> ReplayResult:
    scene_package = package.scene_packages[record.scene_key]
    context = _build_runtime_context(record, package)
    rule_node_map = _build_rule_node_map(scene_package)
    hit_rules: list[str] = []
    reason_codes: list[str] = []
    issues: list[ReplayIssue] = []
    strategy_result = record.strategy_result

    for rule in _enabled_active_rules_in_order(record, package):
        node_id = rule_node_map.get(rule.rule_id)
        if _expression_contains_function(rule.hit_expression):
            matched = False if node_id is None else _match_rule_from_history(record, node_id, rule.rule_id)
        else:
            result = evaluate_expression(rule.hit_expression, context)
            if result.issues:
                matched = False if node_id is None else _match_rule_from_history(record, node_id, rule.rule_id)
            else:
                matched = result.matched

        if not matched:
            continue

        hit_rules.append(rule.rule_id)
        reason_codes.extend(rule.reason_codes)
        context = apply_assignments(rule.assignment_expression, context)
        strategy_result = rule.action

    return ReplayResult(
        record_id=record.record_id,
        scene_key=record.scene_key,
        hit_rules=tuple(hit_rules),
        reason_codes=_dedupe_preserve_order(reason_codes),
        strategy_result=strategy_result,
        issues=tuple(issues),
    )


def replay_records(
    scene_key: str | None = None,
    user_id: str | None = None,
    record_ids: tuple[str, ...] | None = None,
    package: RuleEnginePackage | None = None,
) -> tuple[ReplayResult, ...]:
    package = load_rule_engine_package() if package is None else package
    records = filter_history(scene_key=scene_key, user_id=user_id, package=package)
    if record_ids is not None:
        records = tuple(record for record in records if record.record_id in record_ids)

    results: list[ReplayResult] = []
    for record in records:
        replay_result = replay_record(record, package)
        diff = diff_replay_result(record, replay_result)
        changed = any(field.changed for field in diff.fields)
        results.append(
            ReplayResult(
                record_id=replay_result.record_id,
                scene_key=replay_result.scene_key,
                hit_rules=replay_result.hit_rules,
                reason_codes=replay_result.reason_codes,
                strategy_result=replay_result.strategy_result,
                issues=replay_result.issues,
                changed=changed,
            )
        )
    return tuple(results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay rule engine history.")
    parser.add_argument("--scene")
    parser.add_argument("--user-id")
    parser.add_argument("--record-id", action="append")
    args = parser.parse_args()

    package = load_rule_engine_package()
    results = replay_records(
        scene_key=args.scene,
        user_id=args.user_id,
        record_ids=None if not args.record_id else tuple(args.record_id),
        package=package,
    )
    summary = summarize_replay_results(results, package)
    print(
        f"total_records={summary.total_records} "
        f"changed_records={summary.changed_records} "
        f"unchanged_records={summary.unchanged_records}"
    )
    print(f"strategy_before={summary.strategy_before}")
    print(f"strategy_after={summary.strategy_after}")
    print(f"reason_codes_before={summary.reason_codes_before}")
    print(f"reason_codes_after={summary.reason_codes_after}")
    if summary.rule_hit_difference_counts:
        print("rule_hit_difference_counts:")
        for rule_id, count in sorted(
            summary.rule_hit_difference_counts.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(f"{rule_id}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
