from kittychain.rule_engine.generate_register_scene import _map_rule_variable_refs, _parse_hit_expression


def test_map_rule_variable_refs_rewrites_variable_names_to_keys():
    expression = {
        "and": [
            {
                "var": {
                    "var": "同设备同站点相同邮箱前缀注册次数",
                    "operator": "+",
                    "value": 1,
                },
                "operator": ">",
                "value": 3,
            },
            {
                "var": {"function": "获取邮箱后缀", "args": ["注册邮箱"]},
                "operator": "not in",
                "right_var": "临时禁止注册邮箱列表",
            },
            {"var": "请求时间", "operator": "<", "right_var": "设备限频结束时间点"},
        ]
    }
    assignments = [
        {"var": "羊毛标签", "operator": "set", "value": True},
    ]
    variable_name_to_key = {
        "同设备同站点相同邮箱前缀注册次数": "same_prefix_count",
        "注册邮箱": "register_email",
        "临时禁止注册邮箱列表": "blocked_email_list",
        "请求时间": "request_time",
        "设备限频结束时间点": "rate_limit_end_time",
        "羊毛标签": "wool_label",
    }

    mapped_expression = _map_rule_variable_refs(expression, variable_name_to_key)
    mapped_assignments = _map_rule_variable_refs(assignments, variable_name_to_key)

    assert mapped_expression == {
        "and": [
            {
                "var": {
                    "var": "same_prefix_count",
                    "operator": "+",
                    "value": 1,
                },
                "operator": ">",
                "value": 3,
            },
            {
                "var": {"function": "获取邮箱后缀", "args": ["register_email"]},
                "operator": "not in",
                "right_var": "blocked_email_list",
            },
            {"var": "request_time", "operator": "<", "right_var": "rate_limit_end_time"},
        ]
    }
    assert mapped_assignments == [
        {"var": "wool_label", "operator": "set", "value": True},
    ]


def test_map_rule_variable_refs_rewrites_trimmed_variable_names_to_keys():
    expression = {
        "and": [
            {"var": "同设备1h注册量", "operator": ">", "value": 4},
            {"var": "同设备7d注册量", "operator": ">", "value": 10},
        ]
    }
    variable_name_to_key = {
        "同设备1h注册量": "finger_50933_60m",
        "同设备7d注册量": "finger_50934_168h",
    }

    mapped_expression = _map_rule_variable_refs(expression, variable_name_to_key)

    assert mapped_expression == {
        "and": [
            {"var": "finger_50933_60m", "operator": ">", "value": 4},
            {"var": "finger_50934_168h", "operator": ">", "value": 10},
        ]
    }


def test_parse_hit_expression_wraps_standalone_variable_as_is_true():
    expression = _parse_hit_expression(["特殊国家注册用户"])

    assert expression == {"var": "特殊国家注册用户", "operator": "is true"}
