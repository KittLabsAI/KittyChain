from __future__ import annotations

import argparse
import json

if __package__ in (None, ""):
    from loader import load_rule_engine_package
    from models import HistoryRecord, RiskScene, RuleDefinition, RuleEnginePackage, SceneNode, ScenePackage, VariableDefinition, WorkflowDefinition
else:
    from .loader import load_rule_engine_package
    from .models import HistoryRecord, RiskScene, RuleDefinition, RuleEnginePackage, SceneNode, ScenePackage, VariableDefinition, WorkflowDefinition


def _package_or_default(package: RuleEnginePackage | None) -> RuleEnginePackage:
    return load_rule_engine_package() if package is None else package


def _get_scene_package(scene_key: str, package: RuleEnginePackage) -> ScenePackage:
    try:
        return package.scene_packages[scene_key]
    except KeyError as exc:
        raise KeyError(f"unknown scene: {scene_key}") from exc


def _get_scene_node(scene_package: ScenePackage, node_id: str) -> SceneNode:
    for node in scene_package.nodes:
        if node.node_id == node_id:
            return node
    raise KeyError(f"unknown node: {node_id}")


def list_scenes(package: RuleEnginePackage | None = None) -> tuple[RiskScene, ...]:
    package = _package_or_default(package)
    return package.scenes


def get_scene_workflow(scene_key: str, package: RuleEnginePackage | None = None) -> WorkflowDefinition:
    package = _package_or_default(package)
    return _get_scene_package(scene_key, package).workflow


def list_node_rules(
    scene_key: str,
    node_id: str,
    package: RuleEnginePackage | None = None,
) -> tuple[RuleDefinition, ...]:
    package = _package_or_default(package)
    scene_package = _get_scene_package(scene_key, package)
    node = _get_scene_node(scene_package, node_id)
    rules_by_id = {rule.rule_id: rule for rule in scene_package.rules}
    try:
        return tuple(rules_by_id[rule_ref.rule_id] for rule_ref in node.rule_refs)
    except KeyError as exc:
        raise KeyError(f"unknown rule: {exc.args[0]}") from exc


def get_rule(scene_key: str, rule_id: str, package: RuleEnginePackage | None = None) -> RuleDefinition:
    package = _package_or_default(package)
    scene_package = _get_scene_package(scene_key, package)
    for rule in scene_package.rules:
        if rule.rule_id == rule_id:
            return rule
    raise KeyError(f"unknown rule: {rule_id}")


def list_scene_variables(
    scene_key: str,
    package: RuleEnginePackage | None = None,
) -> tuple[VariableDefinition, ...]:
    package = _package_or_default(package)
    return _get_scene_package(scene_key, package).variables


def list_public_variables(package: RuleEnginePackage | None = None) -> tuple[VariableDefinition, ...]:
    package = _package_or_default(package)
    return package.public_variables


def _record_text(record: HistoryRecord) -> str:
    parts = (
        json.dumps(record.inputs, ensure_ascii=False, sort_keys=True),
        json.dumps(record.derived_variables, ensure_ascii=False, sort_keys=True),
        record.final_decision or "",
    )
    return " ".join(parts).lower()


def filter_history(
    scene_key: str | None = None,
    user_id: str | None = None,
    text: str | None = None,
    package: RuleEnginePackage | None = None,
) -> tuple[HistoryRecord, ...]:
    package = _package_or_default(package)
    text = None if text is None else text.lower()
    records: list[HistoryRecord] = []

    for record in package.history_records:
        if scene_key is not None and record.scene_key != scene_key:
            continue
        if user_id is not None and record.user_id != user_id:
            continue
        if text is not None and text not in _record_text(record):
            continue
        records.append(record)

    return tuple(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the rule engine package.")
    parser.add_argument("--scene")
    parser.add_argument("--user-id")
    parser.add_argument("--text")
    args = parser.parse_args()

    try:
        if args.scene and args.user_id is None and args.text is None:
            workflow = get_scene_workflow(args.scene)
            print(f"scene={args.scene} workflow={workflow.workflow_id}")
            return 0

        if args.scene or args.user_id or args.text:
            records = filter_history(scene_key=args.scene, user_id=args.user_id, text=args.text)
            print(
                f"history_records={len(records)} "
                f"scene={args.scene or '*'} user_id={args.user_id or '*'} text={args.text or '*'}"
            )
            return 0

        package = load_rule_engine_package()
        print(
            f"scenes={len(package.scenes)} "
            f"public_variables={len(package.public_variables)} "
            f"history_records={len(package.history_records)}"
        )
        return 0
    except KeyError as exc:
        print(f"lookup error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
