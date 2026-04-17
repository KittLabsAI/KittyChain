from __future__ import annotations

import json
from pathlib import Path

if __package__ in (None, ""):
    from models import (
        format_rule_engine_summary,
        HistoryRecord,
        RiskScene,
        RuleDefinition,
        RuleEnginePackage,
        RuleReference,
        SceneNode,
        ScenePackage,
        UserLabel,
        VariableDefinition,
        WorkflowDefinition,
        WorkflowEdge,
        WorkflowNode,
    )
else:
    from .models import (
        HistoryRecord,
        RiskScene,
        RuleDefinition,
        RuleEnginePackage,
        RuleReference,
        SceneNode,
        ScenePackage,
        UserLabel,
        VariableDefinition,
        WorkflowDefinition,
        WorkflowEdge,
        WorkflowNode,
        format_rule_engine_summary,
    )


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_risk_scene(data: dict[str, object]) -> RiskScene:
    return RiskScene(
        scene_key=data["scene_key"],
        scene_name=data["scene_name"],
        description=data["description"],
        status=data["status"],
        scene_path=data["scene_path"],
        entry_workflow_id=data["entry_workflow_id"],
        owners=tuple(data["owners"]),
        tags=tuple(data["tags"]),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def _load_workflow_node(data: dict[str, object]) -> WorkflowNode:
    return WorkflowNode(
        node_id=data["node_id"],
        node_type=data["node_type"],
        label=data["label"],
        enabled=data["enabled"],
        position=dict(data["position"]),
    )


def _load_workflow_edge(data: dict[str, object]) -> WorkflowEdge:
    return WorkflowEdge(
        edge_id=data["edge_id"],
        source_node_id=data["source_node_id"],
        target_node_id=data["target_node_id"],
        order=data["order"],
        condition_ref=data.get("condition_ref"),
    )


def _load_workflow(data: dict[str, object]) -> WorkflowDefinition:
    return WorkflowDefinition(
        scene_key=data["scene_key"],
        workflow_id=data["workflow_id"],
        workflow_name=data["workflow_name"],
        entry_node_ids=tuple(data["entry_node_ids"]),
        nodes=tuple(_load_workflow_node(node) for node in data["nodes"]),
        edges=tuple(_load_workflow_edge(edge) for edge in data["edges"]),
        metadata=dict(data["metadata"]),
    )


def _load_rule_reference(data: dict[str, object]) -> RuleReference:
    return RuleReference(
        rule_id=data["rule_id"],
        priority=data["priority"],
        enabled=data["enabled"],
    )


def _load_scene_node(data: dict[str, object]) -> SceneNode:
    return SceneNode(
        node_id=data["node_id"],
        node_name=data["node_name"],
        node_type=data["node_type"],
        description=data["description"],
        rule_refs=tuple(_load_rule_reference(rule_ref) for rule_ref in data["rule_refs"]),
        next_node_ids=tuple(data["next_node_ids"]),
        metadata=dict(data["metadata"]),
    )


def _load_rule_definition(data: dict[str, object]) -> RuleDefinition:
    return RuleDefinition(
        rule_id=data["rule_id"],
        rule_name=data["rule_name"],
        rule_name_cn=data["rule_name_cn"],
        status=data["status"],
        priority=data["priority"],
        hit_expression=data["hit_expression"],
        assignment_expression=list(data["assignment_expression"]),
        action=data["action"],
        reason_codes=tuple(data["reason_codes"]),
        metadata=dict(data["metadata"]),
    )


def _load_variable_definition(data: dict[str, object]) -> VariableDefinition:
    return VariableDefinition(
        variable_key=data["variable_key"],
        variable_name=data["variable_name"],
        scope=data["scope"],
        data_type=data["data_type"],
        description=data["description"],
        source_path=data["source_path"],
        default_value=data["default_value"],
        examples=tuple(data["examples"]),
        searchable=data["searchable"],
        metadata=dict(data.get("metadata", {})),
        shared_by=tuple(data.get("shared_by", [])),
    )


def _load_history_record(data: dict[str, object]) -> HistoryRecord:
    return HistoryRecord(
        record_id=data["record_id"],
        scene_key=data["scene_key"],
        user_id=data["user_id"],
        event_time=data["event_time"],
        inputs=dict(data["inputs"]),
        derived_variables=dict(data["derived_variables"]),
        hit_rules=tuple(data["hit_rules"]),
        strategy_result=data["strategy_result"],
        reason_codes=tuple(data["reason_codes"]),
        final_decision=data.get("final_decision"),
        raw_refs=dict(data["raw_refs"]),
    )


def _load_user_label(data: dict[str, object]) -> UserLabel:
    return UserLabel(
        user_id=data["user_id"],
        label=data["label"],
        label_type=data["label_type"],
        scene_key=data["scene_key"],
        applied_at=data["applied_at"],
        metadata=dict(data["metadata"]),
    )


def load_scene_package(scene_key: str, base_path: Path | None = None) -> ScenePackage:
    root = _default_schema_path() if base_path is None else Path(base_path)
    scene_path = root / "scenes" / scene_key
    workflow_data = _load_json(scene_path / "workflow.json")
    nodes_data = _load_json(scene_path / "nodes.json")
    rules_data = _load_json(scene_path / "rules.json")
    variables_data = _load_json(scene_path / "variables.json")

    return ScenePackage(
        workflow=_load_workflow(workflow_data),
        nodes=tuple(_load_scene_node(node) for node in nodes_data["nodes"]),
        rules=tuple(_load_rule_definition(rule) for rule in rules_data["rules"]),
        variables=tuple(_load_variable_definition(variable) for variable in variables_data["variables"]),
    )


def load_rule_engine_package(base_path: Path | None = None) -> RuleEnginePackage:
    root = _default_schema_path() if base_path is None else Path(base_path)
    scenes_data = _load_json(root / "risk_scenes.json")
    public_variables_data = _load_json(root / "public_variables.json")
    user_labels_data = _load_json(root / "user_labels.json")
    history_data = _load_json(root / "history_data.json")

    scenes = tuple(_load_risk_scene(scene) for scene in scenes_data["scenes"])
    scene_packages = {scene.scene_key: load_scene_package(scene.scene_key, root) for scene in scenes}

    return RuleEnginePackage(
        version=scenes_data["version"],
        generated_at=scenes_data["generated_at"],
        scenes=scenes,
        public_variables=tuple(
            _load_variable_definition(variable) for variable in public_variables_data["variables"]
        ),
        user_labels=tuple(_load_user_label(label) for label in user_labels_data["labels"]),
        history_records=tuple(_load_history_record(record) for record in history_data["records"]),
        scene_packages=scene_packages,
    )


def main() -> int:
    package = load_rule_engine_package()
    for line in format_rule_engine_summary(package):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
