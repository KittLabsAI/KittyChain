from kittychain.rule_engine.evaluator import apply_assignments, evaluate_expression
from kittychain.rule_engine.models import EvaluationResult, ReplayIssue


def test_evaluate_expression_supports_atomic_comparison():
    result = evaluate_expression({"var": "score", "operator": ">", "value": 10}, {"score": 11})

    assert result.matched is True
    assert result.issues == ()


def test_evaluate_expression_supports_boolean_composition():
    expression = {
        "and": [
            {"var": "country", "operator": "=", "value": "US"},
            {"var": "email", "operator": "start with", "value": "risk"},
        ]
    }

    result = evaluate_expression(expression, {"country": "US", "email": "risk-user@example.com"})

    assert result.matched is True


def test_evaluate_expression_supports_arithmetic_in_var_operand():
    result = evaluate_expression(
        {
            "var": {"var": "same_prefix_count", "operator": "+", "value": 1},
            "operator": ">",
            "value": 3,
        },
        {"same_prefix_count": 3},
    )

    assert result.matched is True
    assert result.issues == ()


def test_evaluate_expression_supports_arithmetic_in_value_operand():
    result = evaluate_expression(
        {
            "var": "request_time",
            "operator": "<",
            "right_var": {"var": "limit_end_time", "operator": "-", "value": 1},
        },
        {"request_time": 10, "limit_end_time": 12},
    )

    assert result.matched is True
    assert result.issues == ()


def test_evaluate_expression_supports_right_var_lookup():
    result = evaluate_expression(
        {"var": "request_time", "operator": "<", "right_var": "limit_end_time"},
        {"request_time": 10, "limit_end_time": 12},
    )

    assert result.matched is True
    assert result.issues == ()


def test_evaluate_expression_treats_missing_var_as_none_not_literal_name():
    result = evaluate_expression(
        {
            "and": [
                {"var": "missing_country", "operator": "!=", "right_var": "ip_country"},
                {"var": "missing_country", "operator": "exist"},
            ]
        },
        {"ip_country": "PK"},
    )

    assert result.matched is False
    assert result.issues == ()


def test_evaluate_expression_does_not_match_missing_var_equality_against_missing_right_var():
    result = evaluate_expression(
        {"var": "regUserPwd", "operator": "=", "right_var": "inviterUserPwd"},
        {},
    )

    assert result.matched is False
    assert result.issues == ()


def test_apply_assignments_updates_runtime_context():
    updated = apply_assignments(
        [{"var": "risk_level", "operator": "set", "value": "high"}],
        {"risk_level": "low"},
    )

    assert updated["risk_level"] == "high"


def test_evaluate_expression_supports_whitelisted_function_dispatch():
    result = evaluate_expression(
        {
            "var": {"function": "获取邮箱后缀", "args": ["email"]},
            "operator": "=",
            "value": "gmail.com",
        },
        {"email": "user@gmail.com"},
    )

    assert result.matched is True
    assert result.issues == ()


def test_evaluate_expression_reports_unsupported_operator():
    result = evaluate_expression({"var": "score", "operator": "between", "value": [1, 3]}, {"score": 2})

    assert result.matched is False
    assert result.issues[0].code == "unsupported_operator"


def test_evaluate_expression_reports_unsupported_function():
    result = evaluate_expression(
        {
            "var": {"function": "未知函数", "args": ["email"]},
            "operator": "=",
            "value": "x",
        },
        {"email": "x@example.com"},
    )

    assert result.matched is False
    assert result.issues[0].code == "unsupported_function"


def test_evaluate_expression_reports_arithmetic_errors_without_crashing():
    result = evaluate_expression(
        {"var": "numerator / denominator", "operator": ">", "value": 1},
        {"numerator": 10, "denominator": 0},
    )

    assert result.matched is False
    assert result.issues[0].code == "evaluation_error"


def test_phase3_models_are_typed_and_read_only():
    issue = ReplayIssue(code="unsupported_function", message="missing function", rule_id="rule_demo")
    result = EvaluationResult(matched=False, value=None, issues=(issue,))

    assert result.matched is False
    assert result.issues == (issue,)
