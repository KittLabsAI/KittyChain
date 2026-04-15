import subprocess
import sys
from dataclasses import replace

from kittychain.rule_engine.loader import load_rule_engine_package
from kittychain.rule_engine.models import HistoryRecord, RuleReference, SceneNode, ScenePackage, WorkflowDefinition, WorkflowEdge
from kittychain.rule_engine.validator import validate_rule_engine_package


def test_validate_rule_engine_package_reports_missing_scene_reference():
    package = load_rule_engine_package()
    broken_history = replace(package.history_records[0], scene_key="missing_scene")

    errors = validate_rule_engine_package(replace(package, history_records=(broken_history,)))

    assert len(errors) == 1
    assert errors[0].code == "missing_scene_reference"
    assert "missing_scene" in errors[0].message


def test_validate_rule_engine_package_reports_missing_node_reference():
    package = load_rule_engine_package()
    scene_package = package.scene_packages["demo"]
    broken_edge = WorkflowEdge(
        edge_id="edge_broken",
        source_node_id="node_start",
        target_node_id="node_missing",
        order=None,
        condition_ref=None,
    )
    broken_workflow = replace(scene_package.workflow, edges=scene_package.workflow.edges + (broken_edge,))
    broken_scene_package = replace(scene_package, workflow=broken_workflow)

    errors = validate_rule_engine_package(
        replace(package, scene_packages={"demo": broken_scene_package})
    )

    assert len(errors) == 1
    assert errors[0].code == "missing_node_reference"
    assert "node_missing" in errors[0].message


def test_validate_rule_engine_package_reports_missing_rule_reference():
    package = load_rule_engine_package()
    scene_package = package.scene_packages["demo"]
    node = scene_package.nodes[0]
    broken_node = SceneNode(
        node_id=node.node_id,
        node_name=node.node_name,
        node_type=node.node_type,
        description=node.description,
        rule_refs=node.rule_refs + (RuleReference(rule_id="rule_missing", priority=99, enabled=True),),
        next_node_ids=node.next_node_ids,
        metadata=node.metadata,
    )
    broken_scene_package = replace(scene_package, nodes=(broken_node,) + scene_package.nodes[1:])

    errors = validate_rule_engine_package(
        replace(package, scene_packages={"demo": broken_scene_package})
    )

    assert len(errors) == 1
    assert errors[0].code == "missing_rule_reference"
    assert "rule_missing" in errors[0].message


def test_validator_module_main_reports_clean_package():
    result = subprocess.run(
        [sys.executable, "-m", "kittychain.rule_engine.validator"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "0 validation errors" in result.stdout
    assert "validated scenes=2 rules=112 nodes=19 history_records=2923" in result.stdout


def test_validator_script_main_reports_clean_package():
    result = subprocess.run(
        [sys.executable, "kittychain/rule_engine/validator.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "0 validation errors" in result.stdout
    assert "validated scenes=2 rules=112 nodes=19 history_records=2923" in result.stdout
