import subprocess
import sys
from pathlib import Path

from kittychain.rule_engine.loader import load_rule_engine_package


def test_rule_engine_package_imports():
    import kittychain.rule_engine

    assert kittychain.rule_engine is not None


def test_load_rule_engine_package_reads_demo_and_register_scenes():
    package = load_rule_engine_package()

    assert [scene.scene_key for scene in package.scenes] == ["demo", "register"]
    assert package.scene_packages["demo"].workflow.workflow_id == "workflow_demo_main"
    assert package.scene_packages["register"].workflow.workflow_id == "workflow_register_main"


def test_load_rule_engine_package_returns_typed_models():
    package = load_rule_engine_package()

    demo_scene = package.scenes[0]
    register_scene = package.scenes[1]

    assert demo_scene.scene_name == "Demo Scene"
    assert register_scene.scene_name == "用户注册"
    assert package.public_variables[0].scope == "public"
    assert len(package.public_variables) > 1000
    assert package.history_records[0].record_id == "history_demo_001"
    assert len(package.history_records) == 2923
    assert package.user_labels[0].label == "trusted_user"
    assert len(package.user_labels) == 2923
    assert package.scene_packages["demo"].rules[0].assignment_expression == [
        {"var": "risk_level", "operator": "set", "value": "high"},
    ]


def test_load_rule_engine_package_returns_register_scene_content():
    package = load_rule_engine_package()

    register_scene_package = package.scene_packages["register"]
    register_history = next(record for record in package.history_records if record.scene_key == "register" and record.reason_codes)
    register_label = next(label for label in package.user_labels if label.scene_key == "register")

    assert len(register_scene_package.workflow.nodes) == 22
    assert len(register_scene_package.workflow.edges) == 33
    assert len(register_scene_package.nodes) == 18
    assert len(register_scene_package.rules) == 111
    assert len(register_scene_package.variables) == 295
    assert register_scene_package.workflow.entry_node_ids == ("node_7e0c27f3",)
    assert register_history.scene_key == "register"
    assert register_history.record_id.startswith("history_register_")
    assert register_history.reason_codes == ("R06",)
    assert register_history.strategy_result == "accept"
    assert register_history.final_decision is None
    assert register_label.scene_key == "register"
    assert register_label.label in {"Bad", "Neutral", "Good"}
    device_model_url_public = next(
        variable
        for variable in package.public_variables
        if variable.variable_key == "deviceModel_url_public"
    )
    assert device_model_url_public.variable_name == "设备价值模型接口url_公共"
    assert device_model_url_public.data_type == "string"


def test_load_rule_engine_package_parses_register_rule_expressions():
    package = load_rule_engine_package()

    gps_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "GPS_Concentrate_1H"
    )
    medium_risk_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "Web_SM_Device_MediumRisk"
    )
    start_with_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "StartWithZero"
    )
    white_country_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "whiteCountry"
    )
    minute_device_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "minuteDeviceUseNumberHit"
    )
    day_device_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "dayDeviceUseNumberOf7Hit"
    )
    minute_web_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "minuteWebDeviceUseNumberHit"
    )
    day_web_rule = next(
        rule
        for rule in package.scene_packages["register"].rules
        if rule.rule_id == "dayWebDeviceUseNumberOf7Hit"
    )

    assert gps_rule.hit_expression == {
        "and": [
            {
                "and": [
                    {
                        "var": {
                            "function": "获取对象属性",
                            "args": ["geoInfo", "isoCode"],
                        },
                        "operator": "in",
                        "right_var": "woolConutrys",
                    },
                    {
                        "var": {
                            "function": "获取邮箱后缀",
                            "args": ["regUserEmail"],
                        },
                        "operator": "not in",
                        "right_var": "conf_commonMailbox",
                    },
                ]
            },
            {
                "var": "gps2_50939_1h",
                "operator": ">",
                "value": 30,
            },
        ]
    }
    assert gps_rule.assignment_expression == [
        {"var": "woolTag", "operator": "set", "value": True},
        {"var": "gps1HourHit", "operator": "set", "value": True},
    ]
    assert gps_rule.reason_codes == ("R10",)
    assert medium_risk_rule.hit_expression == {
        "and": [
            {
                "var": "fingerStrategyHitsSm",
                "operator": "=",
                "value": "MEDIUM",
            },
            {
                "var": "fingerIdSm",
                "operator": "exist",
            },
        ]
    }
    assert start_with_rule.hit_expression == {
        "or": [
            {
                "var": "-0",
                "operator": "in",
                "right_var": "regUserPhone",
            },
            {
                "and": [
                    {
                        "var": "-",
                        "operator": "not in",
                        "right_var": "regUserPhone",
                    },
                    {
                        "var": "regUserPhone",
                        "operator": "start with",
                        "value": "0",
                    },
                ]
            },
        ]
    }
    assert white_country_rule.hit_expression == {
        "and": [
            {
                "var": "ip_isoCode_contry",
                "operator": "in",
                "value": ["US", "FR", "GB", "DE", "CA"],
            },
            {
                "var": {
                    "function": "解密函数",
                    "args": ["emailSuffixAes"],
                },
                "operator": "in",
                "value": ["gmail.com", "outlook.com"],
            },
        ]
    }
    assert minute_device_rule.hit_expression["and"][0]["and"][0]["and"][0]["var"] == "finger_50933_60m"
    assert day_device_rule.hit_expression["and"][0]["and"][0]["and"][0]["var"] == "finger_50934_168h"
    assert minute_web_rule.hit_expression["and"][0]["and"][0]["and"][0]["and"][1]["or"][0]["and"][0] == {
        "var": "whiteCountryUser",
        "operator": "is true",
    }
    assert minute_web_rule.hit_expression["and"][0]["and"][0]["and"][0]["and"][1]["or"][0]["and"][1]["var"] == "finger_50933_60m"
    assert day_web_rule.hit_expression["and"][0]["and"][0]["and"][0]["and"][1]["or"][0]["and"][0] == {
        "var": "whiteCountryUser",
        "operator": "is true",
    }
    assert day_web_rule.hit_expression["and"][0]["and"][0]["and"][0]["and"][1]["or"][0]["and"][1]["var"] == "finger_50934_168h"


def test_loader_module_main_prints_package_summary():
    result = subprocess.run(
        [sys.executable, "-m", "kittychain.rule_engine.loader"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "package scenes=2" in result.stdout
    assert "public_variables=1247" in result.stdout
    assert "history_records=2923" in result.stdout
    assert "user_labels=2923" in result.stdout
    assert "scene demo workflow=workflow_demo_main" in result.stdout
    assert "scene register workflow=workflow_register_main" in result.stdout
    assert "nodes=1 rules=1 variables=2 edges=1" in result.stdout
    assert "nodes=18 rules=111 variables=295 edges=33" in result.stdout
    assert "node node_email type=rule rules=rule_disposable_email" in result.stdout
    assert "rule rule_disposable_email action=review priority=1 reason_codes=EMAIL_RISK" in result.stdout


def test_loader_script_main_prints_package_summary():
    result = subprocess.run(
        [sys.executable, "kittychain/rule_engine/loader.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "package scenes=2" in result.stdout
    assert "node node_email type=rule rules=rule_disposable_email" in result.stdout


def test_generated_rule_engine_json_does_not_include_source_file_trace_fields():
    root = Path("kittychain/rule_engine/schemas")
    paths = (
        root / "risk_scenes.json",
        root / "public_variables.json",
        root / "user_labels.json",
        root / "history_data.json",
        root / "scenes" / "register" / "workflow.json",
        root / "scenes" / "register" / "nodes.json",
        root / "scenes" / "register" / "rules.json",
        root / "scenes" / "register" / "variables.json",
    )

    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert "source_file" not in content
        assert "source_row_id" not in content
