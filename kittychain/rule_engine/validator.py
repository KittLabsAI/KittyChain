from __future__ import annotations

from dataclasses import dataclass

if __package__ in (None, ""):
    from loader import load_rule_engine_package
    from models import RuleEnginePackage
else:
    from .loader import load_rule_engine_package
    from .models import RuleEnginePackage


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str
    location: str


def validate_rule_engine_package(package: RuleEnginePackage) -> list[ValidationError]:
    errors: list[ValidationError] = []
    scene_keys = {scene.scene_key for scene in package.scenes}

    for record in package.history_records:
        if record.scene_key not in scene_keys:
            errors.append(
                ValidationError(
                    code="missing_scene_reference",
                    message=f"History record {record.record_id} references missing scene {record.scene_key}.",
                    location=f"history_data.json:{record.record_id}",
                )
            )

    for scene_key, scene_package in package.scene_packages.items():
        node_ids = {node.node_id for node in scene_package.workflow.nodes}
        rule_ids = {rule.rule_id for rule in scene_package.rules}

        for edge in scene_package.workflow.edges:
            if edge.source_node_id not in node_ids:
                errors.append(
                    ValidationError(
                        code="missing_node_reference",
                        message=(
                            f"Workflow edge {edge.edge_id} in scene {scene_key} "
                            f"references missing source node {edge.source_node_id}."
                        ),
                        location=f"scenes/{scene_key}/workflow.json:{edge.edge_id}",
                    )
                )
            if edge.target_node_id not in node_ids:
                errors.append(
                    ValidationError(
                        code="missing_node_reference",
                        message=(
                            f"Workflow edge {edge.edge_id} in scene {scene_key} "
                            f"references missing target node {edge.target_node_id}."
                        ),
                        location=f"scenes/{scene_key}/workflow.json:{edge.edge_id}",
                    )
                )

        for node in scene_package.nodes:
            for rule_ref in node.rule_refs:
                if rule_ref.rule_id not in rule_ids:
                    errors.append(
                        ValidationError(
                            code="missing_rule_reference",
                            message=(
                                f"Scene node {node.node_id} in scene {scene_key} "
                                f"references missing rule {rule_ref.rule_id}."
                            ),
                            location=f"scenes/{scene_key}/nodes.json:{node.node_id}",
                        )
                    )

    return errors


def main() -> int:
    package = load_rule_engine_package()
    errors = validate_rule_engine_package(package)
    print(f"{len(errors)} validation errors")
    if not errors:
        total_rules = sum(len(scene_package.rules) for scene_package in package.scene_packages.values())
        total_nodes = sum(len(scene_package.nodes) for scene_package in package.scene_packages.values())
        print(
            f"validated scenes={len(package.scenes)} "
            f"rules={total_rules} nodes={total_nodes} "
            f"history_records={len(package.history_records)}"
        )
    for error in errors:
        print(f"{error.code} {error.location} {error.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
