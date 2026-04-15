import subprocess
import sys


def test_models_module_main_prints_sample_model_summary():
    result = subprocess.run(
        [sys.executable, "-m", "kittychain.rule_engine.models"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "package scenes=1" in result.stdout
    assert "public_variables=1" in result.stdout
    assert "history_records=1" in result.stdout
    assert "scene demo workflow=workflow_demo_main" in result.stdout
    assert "nodes=1 rules=1 variables=1 edges=1" in result.stdout
    assert "node node_demo type=rule rules=rule_demo" in result.stdout
    assert "rule rule_demo action=review priority=1 reason_codes=DEMO_REASON" in result.stdout


def test_models_script_main_prints_sample_model_summary():
    result = subprocess.run(
        [sys.executable, "kittychain/rule_engine/models.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "package scenes=1" in result.stdout
    assert "node node_demo type=rule rules=rule_demo" in result.stdout
