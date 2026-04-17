from __future__ import annotations

from ast import literal_eval

if __package__ in (None, ""):
    from models import EvaluationResult, ReplayIssue
else:
    from .models import EvaluationResult, ReplayIssue


ARITHMETIC_OPERATORS = {"+", "-", "*", "/"}


def _parse_scalar_token(token: str) -> object:
    if token == "true":
        return True
    if token == "false":
        return False
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    if token.startswith("[") and token.endswith("]"):
        return literal_eval(token)
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        return token


def _resolve_context_token(token: str, context: dict[str, object]) -> object:
    return context.get(token, _parse_scalar_token(token))


def _apply_arithmetic(operator: str, left: object, right: object) -> object:
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        return left / right
    raise KeyError(operator)


def _resolve_arithmetic_expression(value: str, context: dict[str, object]) -> object:
    tokens = value.split()
    if len(tokens) < 3 or not any(token in ARITHMETIC_OPERATORS for token in tokens):
        return context.get(value, value)

    resolved_tokens: list[object] = []
    for token in tokens:
        if token in ARITHMETIC_OPERATORS:
            resolved_tokens.append(token)
        else:
            resolved_tokens.append(_resolve_context_token(token, context))

    for operator_group in ({"*", "/"}, {"+", "-"}):
        while any(token in operator_group for token in resolved_tokens if isinstance(token, str)):
            for index, token in enumerate(resolved_tokens):
                if token not in operator_group:
                    continue
                result = _apply_arithmetic(token, resolved_tokens[index - 1], resolved_tokens[index + 1])
                resolved_tokens[index - 1:index + 2] = [result]
                break
    return resolved_tokens[0]


def _resolve_function_operand(value: dict[str, object], context: dict[str, object]) -> tuple[object | None, tuple[ReplayIssue, ...]]:
    function_name = value["function"]
    args = [context.get(arg, _parse_scalar_token(arg)) if isinstance(arg, str) else arg for arg in value.get("args", [])]

    if function_name == "获取对象属性":
        source, key = args
        if isinstance(source, dict):
            return source.get(key), ()
        return None, ()
    if function_name == "获取邮箱后缀":
        email = args[0]
        if isinstance(email, str) and "@" in email:
            return email.split("@", 1)[1], ()
        return None, ()
    if function_name == "解密函数":
        return args[0], ()

    return None, (
        ReplayIssue(code="unsupported_function", message=f"unsupported function: {function_name}"),
    )


def _resolve_variable_operand(value: object, context: dict[str, object]) -> tuple[object | None, tuple[ReplayIssue, ...]]:
    if isinstance(value, str):
        return context.get(value), ()
    if not isinstance(value, dict):
        return value, ()
    if "operator" in value and "function" not in value and "var" in value:
        return _evaluate_operand_expression(value, context)
    if "function" not in value:
        return value, ()
    return _resolve_function_operand(value, context)


def _resolve_value_operand(value: object, context: dict[str, object]) -> tuple[object | None, tuple[ReplayIssue, ...]]:
    if isinstance(value, str):
        return _resolve_arithmetic_expression(value, context), ()
    if not isinstance(value, dict):
        return value, ()
    if "operator" in value and "function" not in value and "var" in value:
        return _evaluate_operand_expression(value, context)
    if "function" not in value:
        return value, ()
    return _resolve_function_operand(value, context)


def _evaluate_operand_expression(expression: dict[str, object], context: dict[str, object]) -> tuple[object | None, tuple[ReplayIssue, ...]]:
    try:
        left, issues = _resolve_variable_operand(expression.get("var"), context)
        if "right_var" in expression:
            right, right_issues = _resolve_variable_operand(expression.get("right_var"), context)
        else:
            right, right_issues = _resolve_value_operand(expression.get("value"), context)
    except Exception as exc:
        return None, (ReplayIssue(code="evaluation_error", message=str(exc)),)

    combined_issues = issues + right_issues
    if combined_issues:
        return None, combined_issues
    try:
        return _apply_arithmetic(expression["operator"], left, right), ()
    except KeyError:
        return None, (
            ReplayIssue(code="unsupported_operator", message=f"unsupported operator: {expression['operator']}"),
        )
    except Exception as exc:
        return None, (ReplayIssue(code="evaluation_error", message=str(exc)),)


def _compare(operator: object, left: object, right: object) -> bool:
    if operator == "=":
        return left == right
    if operator == "!=":
        return left != right
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == "in":
        return left in right if isinstance(right, (list, tuple, set, str)) else False
    if operator == "not in":
        return left not in right if isinstance(right, (list, tuple, set, str)) else False
    if operator == "exist":
        return left is not None
    if operator == "not exist":
        return left is None
    if operator == "is true":
        return left is True
    if operator == "is false":
        return left is False
    if operator == "start with":
        return isinstance(left, str) and isinstance(right, str) and left.startswith(right)
    raise KeyError(operator)


def evaluate_expression(expression: object, context: dict[str, object]) -> EvaluationResult:
    if isinstance(expression, dict) and "and" in expression:
        issues: list[ReplayIssue] = []
        for item in expression["and"]:
            result = evaluate_expression(item, context)
            issues.extend(result.issues)
            if not result.matched:
                return EvaluationResult(matched=False, value=False, issues=tuple(issues))
        return EvaluationResult(matched=True, value=True, issues=tuple(issues))

    if isinstance(expression, dict) and "or" in expression:
        issues: list[ReplayIssue] = []
        for item in expression["or"]:
            result = evaluate_expression(item, context)
            issues.extend(result.issues)
            if result.matched:
                return EvaluationResult(matched=True, value=True, issues=tuple(issues))
        return EvaluationResult(matched=False, value=False, issues=tuple(issues))

    if not isinstance(expression, dict):
        return EvaluationResult(matched=False, value=None, issues=())

    try:
        left, issues = _resolve_variable_operand(expression.get("var"), context)
        if "right_var" in expression:
            right, right_issues = _resolve_variable_operand(expression.get("right_var"), context)
        else:
            right, right_issues = _resolve_value_operand(expression.get("value"), context)
    except Exception as exc:
        return EvaluationResult(
            matched=False,
            value=None,
            issues=(ReplayIssue(code="evaluation_error", message=str(exc)),),
        )
    combined_issues = issues + right_issues
    if combined_issues:
        return EvaluationResult(matched=False, value=None, issues=combined_issues)

    operator = expression.get("operator")
    if "right_var" in expression and operator in {"=", "!="} and (left is None or right is None):
        return EvaluationResult(matched=False, value=False, issues=())
    try:
        matched = _compare(operator, left, right)
    except KeyError:
        return EvaluationResult(
            matched=False,
            value=None,
            issues=(
                ReplayIssue(code="unsupported_operator", message=f"unsupported operator: {operator}"),
            ),
        )
    except Exception as exc:
        return EvaluationResult(
            matched=False,
            value=None,
            issues=(ReplayIssue(code="evaluation_error", message=str(exc)),),
        )

    return EvaluationResult(matched=matched, value=matched, issues=())


def apply_assignments(assignments: object, context: dict[str, object]) -> dict[str, object]:
    updated = dict(context)
    for assignment in assignments:
        if assignment.get("operator") == "set":
            updated[assignment["var"]] = assignment.get("value")
    return updated
