# Lightweight Rule Engine

## Purpose

This directory defines a lightweight rule engine for KittyChain.

The engine is designed around a stable JSON package instead of direct CSV or Markdown parsing. The package is intended to support:

- multiple risk scenes
- scene-level workflow browsing
- node and rule inspection
- variable browsing
- historical decision search
- future adapters that normalize user-provided files into one standard format

This first version focuses on clear standards and development boundaries. It does not assume compatibility with the existing `strategy_simulation` or `read_*` tools.

## Design Principles

- Use JSON as the canonical internal format.
- Separate scene-local data from cross-scene shared data.
- Keep workflow structure, node membership, rule definitions, variable definitions, and history records as different concerns.
- Do not guess business meaning when source data is ambiguous.
- Keep the standardized JSON package self-sufficient so the engine can run without original source files.

## Directory Layout

```text
kittychain/rule_engine/
  README.md
  SCHEMA_TEMPLATE.md
  ADAPTER_CONTRACT.md
  PLAN.md
  schemas/
    risk_scenes.json
    public_variables.json
    user_labels.json
    history_data.json
    scenes/
      <scene_key>/
        workflow.json
        nodes.json
        rules.json
        variables.json
```

## Standard Package

The standard package contains eight JSON files.

### Global Files

1. `risk_scenes.json`
- The entry point for all risk scenes.
- Used by the home page scene list.

2. `public_variables.json`
- Shared variable definitions used across multiple scenes.
- Used by the home page public variables page.

3. `user_labels.json`
- User labels and label metadata.
- Used as supporting data for analysis and future rule workflows.

4. `history_data.json`
- Normalized historical request and decision records.
- Used by the home page history logs page.

### Scene-Local Files

Each scene lives under `schemas/scenes/<scene_key>/`.

1. `workflow.json`
- Defines the workflow graph.
- Includes nodes, edges, routing metadata, and visual layout metadata.

2. `nodes.json`
- Defines scene nodes and the rules contained by each node.
- Used by the node page.

3. `rules.json`
- Defines normalized rule logic.
- Includes hit logic, assignment logic, action, and reason codes.
- Used by the rule detail modal.

4. `variables.json`
- Defines scene-private variables.
- Includes both input variables and derived variables.
- Used by the scene variables tab.

## Core Concepts

### Risk Scene

A risk scene is an independently managed strategy domain, such as registration risk, KYC risk, withdrawal risk, or payment fraud review.

Each scene has:

- one stable `scene_key`
- one workflow
- one node set
- one rule set
- one private variable set
- many history records

### Workflow

A workflow is the scene-level graph that describes how execution can move between nodes. It captures structure and routing, not rule detail.

### Node

A node is a workflow unit. A node may represent:

- an entry point
- a condition branch
- a rule container
- a collection step
- an end state

Nodes reference rules, but do not duplicate rule logic.

### Rule

A rule is the smallest decision unit in the engine. A normalized rule contains:

- stable identity
- display name
- hit expression
- assignment expression
- action
- reason codes

### Expression Format

Normalized rule expressions should use structured JSON rather than raw source-system expression strings.

Supported operators in `hit_expression`:

- `=`
- `!=`
- `>`
- `>=`
- `<`
- `in`
- `not in`
- `exist`
- `not exist`
- `is true`
- `is false`
- `start with`
- `and`
- `or`

Formatting rules:

- `hit_expression` should contain only normalized hit logic.
- Atomic hit expressions use objects such as `{"var": "ip国家码(解析)", "operator": "in", "value": ["US", "FR"]}`.
- Function operands use nested objects such as `{"function": "解密函数", "args": ["邮箱域名(aes密文)"]}`.
- Boolean composition uses binary objects such as `{"and": [expr1, expr2]}` or `{"or": [expr1, expr2]}`.
- `and` and `or` only combine two expressions at a time.
- Parentheses in the source expression define grouping priority. Without grouping, boolean expressions are combined in source order.
- `assignment_expression` should contain only post-hit assignments.
- `assignment_expression` uses an array of assignment objects such as `[{"var": "risk_level", "operator": "set", "value": "high"}]`.
- `assignment_expression` must not use string forms like `set a = b`.

### Data Types

The rule engine supports these normalized variable data types:

- `double`
- `string`
- `long`
- `list`
- `bool`
- `map`
- `other`

For adapter-generated variables that come from a source `data_type` field, the mapping is:

- `1` -> `double`
- `2` -> `string`
- `3` -> `long`
- `4` -> `list`
- `5` -> `bool`
- `6` -> `map`
- `7` -> `other`

If a source dataset uses an out-of-range or undocumented type code, the adapter should normalize it to `other` rather than guessing a narrower type.

### Variable

Variables are normalized data fields used by rules and history.

Supported categories:

- `input`
- `derived`
- `public`

### History Record

A history record is one normalized execution event. It should preserve:

- scene association
- user identity
- inputs
- derived variables
- hit rules
- strategy result
- reason codes

## Relationship Model

```text
risk_scenes.json
  -> scene_key
  -> scenes/<scene_key>/workflow.json
  -> scenes/<scene_key>/nodes.json
  -> scenes/<scene_key>/rules.json
  -> scenes/<scene_key>/variables.json

history_data.json
  -> scene_key
  -> user_id
  -> inputs / derived_variables / hit_rules / reason_codes

public_variables.json
  -> shared variable definitions

user_labels.json
  -> user_id
```

## Data Conventions

- All timestamps should use ISO 8601 strings.
- All top-level metadata keys should use snake_case.
- `scene_key` is the primary cross-file scene reference.
- `reason_codes` must always be an array.
- `inputs` and `derived_variables` must always be JSON objects.
- Stable source IDs should be preserved when available.
- The standard schema should not include a top-level `source` field in rules, history records, or user labels.
- If a field is unknown, use `null`, `{}`, or `[]` based on the expected type rather than guessing.
- If `strategy_result` is `pass` but `reason_codes` is not empty, the record is still an explicit decision record and must not be treated as a miss.

## Minimal Example

The example below shows one scene called `register`.

### `risk_scenes.json`

```json
{
  "version": "1.0",
  "generated_at": "2026-04-15T10:00:00Z",
  "scenes": [
    {
      "scene_key": "register",
      "scene_name": "User Registration",
      "description": "Registration risk controls.",
      "status": "active",
      "scene_path": "schemas/scenes/register",
      "entry_workflow_id": "workflow_register_main",
      "owners": ["risk-team"],
      "tags": ["registration", "fraud"],
      "created_at": "2026-04-15T10:00:00Z",
      "updated_at": "2026-04-15T10:00:00Z"
    }
  ]
}
```

### `workflow.json`

```json
{
  "scene_key": "register",
  "workflow_id": "workflow_register_main",
  "workflow_name": "Registration Main Flow",
  "entry_node_ids": ["node_start"],
  "nodes": [
    {
      "node_id": "node_start",
      "node_type": "init",
      "label": "Start",
      "enabled": true,
      "position": {"x": 0, "y": 0}
    },
    {
      "node_id": "node_email",
      "node_type": "rule",
      "label": "Email Rules",
      "enabled": true,
      "position": {"x": 240, "y": 0}
    }
  ],
  "edges": [
    {
      "edge_id": "edge_start_email",
      "source_node_id": "node_start",
      "target_node_id": "node_email",
      "order": 1
    }
  ],
  "metadata": {}
}
```

### `nodes.json`

```json
{
  "scene_key": "register",
  "nodes": [
    {
      "node_id": "node_email",
      "node_name": "Email Rules",
      "node_type": "rule",
      "description": "Email-related risk rules.",
      "rule_refs": [
        {
          "rule_id": "rule_hour_email_use",
          "priority": 6,
          "enabled": true
        }
      ],
      "next_node_ids": [],
      "metadata": {}
    }
  ]
}
```

### `rules.json`

```json
{
  "scene_key": "register",
  "rules": [
    {
      "rule_id": "rule_hour_email_use",
      "rule_name": "hourEmailUseNumberHit",
      "rule_name_cn": "Email registrations exceed threshold in 24h",
      "status": "active",
      "priority": 6,
      "hit_expression": {
        "var": "hourEmailUseNumberHit",
        "operator": "is true"
      },
      "assignment_expression": [
        {
          "var": "risk_level",
          "operator": "set",
          "value": "review"
        }
      ],
      "action": "review",
      "reason_codes": ["EMAIL_24H_THRESHOLD"],
      "metadata": {}
    }
  ]
}
```

### `variables.json`

```json
{
  "scene_key": "register",
  "variables": [
    {
      "variable_key": "request_time",
      "variable_name": "Request Time",
      "scope": "input",
      "data_type": "string",
      "description": "Original request timestamp.",
      "source_path": "s.requestTime",
      "default_value": null,
      "examples": ["1772297691862"],
      "searchable": true
    },
    {
      "variable_key": "hour_email_use_number_hit",
      "variable_name": "Email threshold hit in 24h",
      "scope": "derived",
      "data_type": "bool",
      "description": "Whether the email count threshold was hit.",
      "source_path": "e.hourEmailUseNumberHit",
      "default_value": false,
      "examples": [true],
      "searchable": true
    }
  ]
}
```

### `public_variables.json`

```json
{
  "version": "1.0",
  "variables": [
    {
      "variable_key": "user_id",
      "variable_name": "User ID",
      "scope": "public",
      "data_type": "string",
      "description": "Stable user identifier.",
      "shared_by": ["register"]
    }
  ]
}
```

### `history_data.json`

```json
{
  "version": "1.0",
  "records": [
    {
      "record_id": "hist_register_0001",
      "scene_key": "register",
      "user_id": "u1",
      "event_time": "2026-03-01T00:54:52Z",
      "inputs": {
        "requestTime": "1772297691862",
        "platform": "ANDROID_APP"
      },
      "derived_variables": {
        "hourEmailUseNumberHit": true
      },
      "hit_rules": ["rule_hour_email_use"],
      "strategy_result": "review",
      "reason_codes": ["EMAIL_24H_THRESHOLD"],
      "final_decision": "review",
      "raw_refs": {}
    }
  ]
}
```

### `user_labels.json`

```json
{
  "version": "1.0",
  "labels": [
    {
      "user_id": "u1",
      "label": "Bad",
      "label_type": "risk_outcome",
      "scene_key": "register",
      "applied_at": "2026-03-01T00:00:00Z",
      "metadata": {}
    }
  ]
}
```

## Intended Consumers

This directory is intended to support three types of consumers:

- Python rule engine code
- future UI pages
- adapter subagents that convert arbitrary user-provided data into the standard package

For exact field expectations, read [SCHEMA_TEMPLATE.md](/Users/kc/Desktop/个人资料/个人项目/KittyChain/kittychain/rule_engine/SCHEMA_TEMPLATE.md).

For adapter execution rules, read [ADAPTER_CONTRACT.md](/Users/kc/Desktop/个人资料/个人项目/KittyChain/kittychain/rule_engine/ADAPTER_CONTRACT.md).
