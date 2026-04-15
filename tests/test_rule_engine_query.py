import subprocess
import sys

from kittychain.rule_engine.loader import load_rule_engine_package
from kittychain.rule_engine.query import (
    filter_history,
    get_rule,
    get_scene_workflow,
    list_node_rules,
    list_public_variables,
    list_scene_variables,
    list_scenes,
)


def test_list_scenes_returns_scene_order_from_package():
    scenes = list_scenes()

    assert [scene.scene_key for scene in scenes] == ["demo", "register"]


def test_get_scene_workflow_returns_register_workflow():
    workflow = get_scene_workflow("register")

    assert workflow.workflow_id == "workflow_register_main"
    assert workflow.entry_node_ids == ("node_7e0c27f3",)


def test_list_node_rules_returns_rules_in_node_reference_order():
    rules = list_node_rules("register", "node_0ce89b07")

    assert [rule.rule_id for rule in rules[:3]] == [
        "Web_SM_Device_MediumRisk",
        "Web_SM_Device_HighRisk",
        "r_web_finger_examption",
    ]


def test_get_rule_returns_named_rule_definition():
    rule = get_rule("register", "Web_SM_Device_MediumRisk")

    assert rule.action == "pass"
    assert rule.reason_codes == ()


def test_list_scene_variables_returns_register_private_variables():
    variables = list_scene_variables("register")

    assert len(variables) == 295
    assert "deviceModel_url_public" not in {variable.variable_key for variable in variables}


def test_list_public_variables_returns_global_variables():
    variables = list_public_variables()

    assert len(variables) == 1247
    assert "deviceModel_url_public" in {variable.variable_key for variable in variables}


def test_filter_history_supports_scene_and_user_filters():
    package = load_rule_engine_package()
    sample_record = next(record for record in package.history_records if record.scene_key == "register")

    records = filter_history(scene_key="register", user_id=sample_record.user_id)

    assert records
    assert all(record.scene_key == "register" for record in records)
    assert all(record.user_id == sample_record.user_id for record in records)


def test_filter_history_matches_input_text_case_insensitively():
    records = filter_history(text="4.15.1")

    assert records


def test_filter_history_matches_derived_variable_text_case_insensitively():
    records = filter_history(text="3.5032583359332046")

    assert records


def test_filter_history_matches_final_decision_text_case_insensitively():
    records = filter_history(text="review")

    assert records


def test_query_module_main_prints_package_summary():
    result = subprocess.run(
        [sys.executable, "-m", "kittychain.rule_engine.query"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "scenes=2" in result.stdout
    assert "public_variables=1247" in result.stdout
    assert "history_records=2923" in result.stdout


def test_query_script_main_filters_history():
    result = subprocess.run(
        [sys.executable, "kittychain/rule_engine/query.py", "--scene", "register", "--text", "review"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "history_records=" in result.stdout
    assert "scene=register" in result.stdout
