from __future__ import annotations

if __package__ in (None, ""):
    from models import FieldDiff, ReplayDiff, ReplayResult, ReplaySummary, RuleEnginePackage
else:
    from .models import FieldDiff, ReplayDiff, ReplayResult, ReplaySummary, RuleEnginePackage


def diff_replay_result(record, replay_result: ReplayResult) -> ReplayDiff:
    fields = (
        FieldDiff(
            field_name="hit_rules",
            before=record.hit_rules,
            after=replay_result.hit_rules,
            changed=set(record.hit_rules) != set(replay_result.hit_rules),
        ),
        FieldDiff(
            field_name="reason_codes",
            before=record.reason_codes,
            after=replay_result.reason_codes,
            changed=set(record.reason_codes) != set(replay_result.reason_codes),
        ),
        FieldDiff(
            field_name="strategy_result",
            before=record.strategy_result,
            after=replay_result.strategy_result,
            changed=record.strategy_result != replay_result.strategy_result,
        ),
    )
    return ReplayDiff(record_id=record.record_id, fields=fields)


def _enabled_rule_node_maps(package: RuleEnginePackage) -> dict[str, dict[str, str]]:
    scene_rule_nodes: dict[str, dict[str, str]] = {}
    for scene_key, scene_package in package.scene_packages.items():
        rule_nodes: dict[str, str] = {}
        for node in scene_package.nodes:
            for rule_ref in node.rule_refs:
                if not rule_ref.enabled:
                    continue
                rule_nodes.setdefault(rule_ref.rule_id, node.node_id)
        scene_rule_nodes[scene_key] = rule_nodes
    return scene_rule_nodes


def summarize_replay_results(
    results: tuple[ReplayResult, ...],
    package: RuleEnginePackage,
) -> ReplaySummary:
    strategy_before: dict[str, int] = {}
    strategy_after: dict[str, int] = {}
    reason_codes_before: dict[str, int] = {}
    reason_codes_after: dict[str, int] = {}
    records_by_id = {record.record_id: record for record in package.history_records}
    scene_rule_nodes = _enabled_rule_node_maps(package)
    rule_hit_difference_counts: dict[str, int] = {}

    changed_records = 0
    for result in results:
        record = records_by_id[result.record_id]
        if result.changed:
            changed_records += 1
        strategy_before[record.strategy_result or ""] = strategy_before.get(record.strategy_result or "", 0) + 1
        strategy_after[result.strategy_result or ""] = strategy_after.get(result.strategy_result or "", 0) + 1
        for code in record.reason_codes:
            reason_codes_before[code] = reason_codes_before.get(code, 0) + 1
        for code in result.reason_codes:
            reason_codes_after[code] = reason_codes_after.get(code, 0) + 1

        inner_rule_result = record.derived_variables.get("inner_rule_result")
        if not isinstance(inner_rule_result, dict):
            continue

        replay_hits = set(result.hit_rules)
        for rule_id, node_id in scene_rule_nodes.get(result.scene_key, {}).items():
            history_hit = bool(inner_rule_result.get(f"{node_id}.{rule_id}", False))
            replay_hit = rule_id in replay_hits
            if history_hit == replay_hit:
                continue
            rule_hit_difference_counts[rule_id] = rule_hit_difference_counts.get(rule_id, 0) + 1

    return ReplaySummary(
        total_records=len(results),
        changed_records=changed_records,
        unchanged_records=len(results) - changed_records,
        rule_hit_difference_counts=rule_hit_difference_counts,
        strategy_before=strategy_before,
        strategy_after=strategy_after,
        reason_codes_before=reason_codes_before,
        reason_codes_after=reason_codes_after,
    )
