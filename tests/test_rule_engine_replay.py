import subprocess
import sys

from kittychain.rule_engine.diff import diff_replay_result, summarize_replay_results
from kittychain.rule_engine.loader import load_rule_engine_package
from kittychain.rule_engine.replay import _enabled_rules_in_order, replay_record, replay_records


def test_replay_record_returns_typed_result_for_demo_scene():
    package = load_rule_engine_package()
    record = next(record for record in package.history_records if record.scene_key == "demo")

    result = replay_record(record, package)

    assert result.record_id == record.record_id
    assert result.strategy_result == "review"


def test_replay_record_marks_register_history_as_changed_or_unchanged():
    package = load_rule_engine_package()
    record = next(record for record in package.history_records if record.scene_key == "register")

    result = replay_record(record, package)

    assert result.record_id == record.record_id
    assert isinstance(result.changed, bool)


def test_diff_replay_result_compares_historical_and_replayed_outputs():
    package = load_rule_engine_package()
    record = next(record for record in package.history_records if record.scene_key == "demo")
    result = replay_record(record, package)

    diff = diff_replay_result(record, result)

    assert [field.field_name for field in diff.fields] == [
        "hit_rules",
        "reason_codes",
        "strategy_result",
    ]


def test_replay_records_filters_by_scene_and_user():
    package = load_rule_engine_package()
    record = next(record for record in package.history_records if record.scene_key == "register")

    results = replay_records(scene_key="register", user_id=record.user_id, package=package)

    assert results
    assert all(result.scene_key == "register" for result in results)


def test_replay_records_summary_counts_changed_unchanged_and_unsupported():
    package = load_rule_engine_package()

    results = replay_records(scene_key="demo", package=package)
    summary = summarize_replay_results(results, package)

    assert summary.total_records == len(results)
    assert summary.changed_records + summary.unchanged_records == len(results)
    assert summary.rule_hit_difference_counts == {}


def test_replay_records_summary_includes_rule_hit_difference_counts():
    package = load_rule_engine_package()

    results = replay_records(scene_key="register", package=package)
    summary = summarize_replay_results(results, package)

    assert summary.rule_hit_difference_counts == {}
    assert "SMS_IP_Country_Conflict" not in summary.rule_hit_difference_counts
    assert "Web_SM_Device_MediumRisk" not in summary.rule_hit_difference_counts


def test_replay_record_uses_history_inner_rule_result_for_function_rule_hit():
    package = load_rule_engine_package()
    record = next(
        item
        for item in package.history_records
        if item.record_id == "history_register_69a387be05ae4b00017ce077"
    )

    result = replay_record(record, package)

    assert "bulkRegDetectModelHighRiskCountry" in result.hit_rules
    assert not any(issue.code == "unsupported_function" for issue in result.issues)


def test_replay_record_skips_unsupported_issue_for_function_rule_history_miss():
    package = load_rule_engine_package()
    record = next(
        item
        for item in package.history_records
        if item.record_id == "history_register_69a31ddbfedd740001d8da08"
    )

    result = replay_record(record, package)

    assert not any(issue.rule_id == "VN_temp_Email_Reject" for issue in result.issues)


def test_replay_record_skips_disabled_rules_from_nodes():
    package = load_rule_engine_package()
    record = next(
        item
        for item in package.history_records
        if item.record_id == "history_register_69a3b700ef7e4a00012773d4"
    )

    result = replay_record(record, package)

    assert "r_web_finger_examption" not in result.hit_rules
    assert not any(issue.rule_id == "r_web_finger_examption" for issue in result.issues)


def test_replay_record_uses_history_inner_rule_result_when_rule_evaluation_errors():
    package = load_rule_engine_package()
    record = next(
        item
        for item in package.history_records
        if item.record_id == "history_register_69a31ddbfedd740001d8da08"
    )

    result = replay_record(record, package)

    assert not any(issue.rule_id == "rateLimit" for issue in result.issues)
    assert not any(issue.rule_id == "ipRateLimit" for issue in result.issues)


def test_replay_record_does_not_use_variable_defaults_for_missing_values():
    package = load_rule_engine_package()
    record = next(
        item
        for item in package.history_records
        if item.record_id == "history_register_69a3b79015b60600014a2b12"
    )

    result = replay_record(record, package)

    assert "SMS_IP_Country_Conflict" not in result.hit_rules


def test_replay_record_respects_workflow_condition_before_evaluating_web_node_rules():
    package = load_rule_engine_package()
    record = next(
        item
        for item in package.history_records
        if item.record_id == "history_register_69a3b066f93f630001e1b1a5"
    )

    result = replay_record(record, package)

    assert "Web_SM_Device_MediumRisk" not in result.hit_rules


def test_replay_record_does_not_match_same_pwd_when_both_passwords_are_missing():
    package = load_rule_engine_package()
    record = next(
        item
        for item in package.history_records
        if item.record_id == "history_register_69a3abf857a47a00010e2381"
    )

    result = replay_record(record, package)

    assert "samePwd" not in result.hit_rules


def test_enabled_rules_in_order_follows_rule_reference_priority():
    package = load_rule_engine_package()
    scene_package = package.scene_packages["register"]

    ordered_rules = _enabled_rules_in_order(scene_package)
    web_rule_ids = [
        rule.rule_id
        for rule in ordered_rules
        if rule.rule_id in {
            "Web_SM_Device_MediumRisk",
            "Web_SM_Device_HighRisk",
            "whiteCountry",
        }
    ]

    assert web_rule_ids == [
        "Web_SM_Device_MediumRisk",
        "Web_SM_Device_HighRisk",
        "whiteCountry",
    ]


def test_replay_module_main_prints_summary():
    result = subprocess.run(
        [sys.executable, "-m", "kittychain.rule_engine.replay", "--scene", "demo"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "total_records=" in result.stdout
