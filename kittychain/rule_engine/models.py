from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskScene:
    scene_key: str
    scene_name: str
    description: str | None
    status: str
    scene_path: str
    entry_workflow_id: str | None
    owners: tuple[str, ...]
    tags: tuple[str, ...]
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class WorkflowNode:
    node_id: str
    node_type: str
    label: str
    enabled: bool
    position: dict[str, float]


@dataclass(frozen=True)
class WorkflowEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    order: int | None
    condition_ref: str | None


@dataclass(frozen=True)
class WorkflowDefinition:
    scene_key: str
    workflow_id: str
    workflow_name: str
    entry_node_ids: tuple[str, ...]
    nodes: tuple[WorkflowNode, ...]
    edges: tuple[WorkflowEdge, ...]
    metadata: dict[str, object]


@dataclass(frozen=True)
class RuleReference:
    rule_id: str
    priority: int | None
    enabled: bool


@dataclass(frozen=True)
class SceneNode:
    node_id: str
    node_name: str
    node_type: str
    description: str | None
    rule_refs: tuple[RuleReference, ...]
    next_node_ids: tuple[str, ...]
    metadata: dict[str, object]


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    rule_name: str
    rule_name_cn: str | None
    status: str
    priority: int | None
    hit_expression: object
    assignment_expression: object
    action: str
    reason_codes: tuple[str, ...]
    metadata: dict[str, object]


@dataclass(frozen=True)
class VariableDefinition:
    variable_key: str
    variable_name: str
    scope: str
    data_type: str
    description: str | None
    source_path: str | None
    default_value: object
    examples: tuple[object, ...]
    searchable: bool
    metadata: dict[str, object]
    shared_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoryRecord:
    record_id: str
    scene_key: str
    user_id: str | None
    event_time: str | None
    inputs: dict[str, object]
    derived_variables: dict[str, object]
    hit_rules: tuple[str, ...]
    strategy_result: str | None
    reason_codes: tuple[str, ...]
    final_decision: str | None
    raw_refs: dict[str, object]


@dataclass(frozen=True)
class UserLabel:
    user_id: str
    label: str
    label_type: str | None
    scene_key: str | None
    applied_at: str | None
    metadata: dict[str, object]


@dataclass(frozen=True)
class ScenePackage:
    workflow: WorkflowDefinition
    nodes: tuple[SceneNode, ...]
    rules: tuple[RuleDefinition, ...]
    variables: tuple[VariableDefinition, ...]


@dataclass(frozen=True)
class RuleEnginePackage:
    version: str
    generated_at: str | None
    scenes: tuple[RiskScene, ...]
    public_variables: tuple[VariableDefinition, ...]
    user_labels: tuple[UserLabel, ...]
    history_records: tuple[HistoryRecord, ...]
    scene_packages: dict[str, ScenePackage]


@dataclass(frozen=True)
class ReplayIssue:
    code: str
    message: str
    rule_id: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    matched: bool
    value: object | None
    issues: tuple[ReplayIssue, ...]


@dataclass(frozen=True)
class FieldDiff:
    field_name: str
    before: object
    after: object
    changed: bool


@dataclass(frozen=True)
class ReplayDiff:
    record_id: str
    fields: tuple[FieldDiff, ...]


@dataclass(frozen=True)
class ReplayResult:
    record_id: str
    scene_key: str
    hit_rules: tuple[str, ...]
    reason_codes: tuple[str, ...]
    strategy_result: str | None
    issues: tuple[ReplayIssue, ...]
    changed: bool = False


@dataclass(frozen=True)
class ReplaySummary:
    total_records: int
    changed_records: int
    unchanged_records: int
    rule_hit_difference_counts: dict[str, int]
    strategy_before: dict[str, int]
    strategy_after: dict[str, int]
    reason_codes_before: dict[str, int]
    reason_codes_after: dict[str, int]


def build_demo_rule_engine_package() -> RuleEnginePackage:
    workflow_node = WorkflowNode(
        node_id="node_demo",
        node_type="rule",
        label="Demo Node",
        enabled=True,
        position={"x": 0.0, "y": 0.0},
    )
    workflow_edge = WorkflowEdge(
        edge_id="edge_demo",
        source_node_id="node_demo",
        target_node_id="node_demo",
        order=1,
        condition_ref=None,
    )
    workflow = WorkflowDefinition(
        scene_key="demo",
        workflow_id="workflow_demo_main",
        workflow_name="Demo Workflow",
        entry_node_ids=("node_demo",),
        nodes=(workflow_node,),
        edges=(workflow_edge,),
        metadata={},
    )
    rule_reference = RuleReference(rule_id="rule_demo", priority=1, enabled=True)
    scene_node = SceneNode(
        node_id="node_demo",
        node_name="Demo Scene Node",
        node_type="rule",
        description="Demo node for manual verification.",
        rule_refs=(rule_reference,),
        next_node_ids=(),
        metadata={},
    )
    rule = RuleDefinition(
        rule_id="rule_demo",
        rule_name="demo_rule",
        rule_name_cn=None,
        status="active",
        priority=1,
        hit_expression={
            "var": "demo_input",
            "operator": "is true",
        },
        assignment_expression=[
            {
                "var": "demo_output",
                "operator": "set",
                "value": "review",
            }
        ],
        action="review",
        reason_codes=("DEMO_REASON",),
        metadata={},
    )
    variable = VariableDefinition(
        variable_key="demo_var",
        variable_name="Demo Variable",
        scope="derived",
        data_type="string",
        description="Demo derived variable.",
        source_path="e.demo_var",
        default_value="",
        examples=("value",),
        searchable=True,
        metadata={},
    )
    public_variable = VariableDefinition(
        variable_key="public_demo_var",
        variable_name="Public Demo Variable",
        scope="public",
        data_type="number",
        description="Demo public variable.",
        source_path="shared.demo_var",
        default_value=0,
        examples=(1,),
        searchable=True,
        metadata={},
        shared_by=("demo",),
    )
    scene = RiskScene(
        scene_key="demo",
        scene_name="Demo Scene",
        description="Minimal manual verification sample.",
        status="active",
        scene_path="schemas/scenes/demo",
        entry_workflow_id="workflow_demo_main",
        owners=("risk-team",),
        tags=("demo",),
        created_at=None,
        updated_at=None,
    )
    history_record = HistoryRecord(
        record_id="history_demo",
        scene_key="demo",
        user_id="user_demo",
        event_time=None,
        inputs={"demo_input": True},
        derived_variables={"demo_var": "value"},
        hit_rules=("rule_demo",),
        strategy_result="review",
        reason_codes=("DEMO_REASON",),
        final_decision="manual_review",
        raw_refs={},
    )
    user_label = UserLabel(
        user_id="user_demo",
        label="demo_label",
        label_type="demo",
        scene_key="demo",
        applied_at=None,
        metadata={},
    )
    scene_package = ScenePackage(
        workflow=workflow,
        nodes=(scene_node,),
        rules=(rule,),
        variables=(variable,),
    )
    return RuleEnginePackage(
        version="1.0",
        generated_at=None,
        scenes=(scene,),
        public_variables=(public_variable,),
        user_labels=(user_label,),
        history_records=(history_record,),
        scene_packages={"demo": scene_package},
    )


def format_rule_engine_summary(package: RuleEnginePackage) -> list[str]:
    lines = [
        (
            f"package scenes={len(package.scenes)} "
            f"public_variables={len(package.public_variables)} "
            f"history_records={len(package.history_records)} "
            f"user_labels={len(package.user_labels)}"
        )
    ]
    for scene in package.scenes:
        scene_package = package.scene_packages[scene.scene_key]
        lines.append(
            (
                f"scene {scene.scene_key} workflow={scene_package.workflow.workflow_id} "
                f"nodes={len(scene_package.nodes)} rules={len(scene_package.rules)} "
                f"variables={len(scene_package.variables)} edges={len(scene_package.workflow.edges)}"
            )
        )
        for node in scene_package.nodes:
            rule_ids = ",".join(rule_ref.rule_id for rule_ref in node.rule_refs)
            lines.append(
                f"node {node.node_id} type={node.node_type} rules={rule_ids}"
            )
        for rule in scene_package.rules:
            reason_codes = ",".join(rule.reason_codes)
            lines.append(
                (
                    f"rule {rule.rule_id} action={rule.action} "
                    f"priority={rule.priority} reason_codes={reason_codes}"
                )
            )
    return lines


def main() -> int:
    for line in format_rule_engine_summary(build_demo_rule_engine_package()):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
