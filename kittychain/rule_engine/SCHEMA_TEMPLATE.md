# Schema Template

## Purpose

This document defines the standard JSON package expected by the KittyChain lightweight rule engine.

It is intended to be precise enough for:

- human implementers
- validators
- adapter agents that need a stable target format

This document defines structure, required fields, conventions, and minimal examples. It does not define how an adapter should behave when source input is ambiguous. That behavior is defined in [ADAPTER_CONTRACT.md](/Users/kc/Desktop/个人资料/个人项目/KittyChain/kittychain/rule_engine/ADAPTER_CONTRACT.md).

## Global Conventions

### Naming

- JSON keys must use snake_case.
- Stable source IDs may preserve source naming style in values.
- `scene_key` is the required scene-level reference key across files.

### Time

- All timestamps must use ISO 8601 strings.
- If the source only provides a date, use date-only ISO format.

### Collections

- Arrays must be used for repeated items.
- Maps must be used for flexible key-value payloads such as `inputs` and `derived_variables`.

### Nullability

- Unknown scalar values should use `null`.
- Unknown collections should use empty arrays or empty objects.
- Do not replace unknown values with guessed defaults.

### Enumerations

- `action`: `pass`, `review`, `reject`
- `status`: `active`, `inactive`, `draft`, `archived`
- `scope`: `input`, `derived`, `public`
- `node_type`: `init`, `condition`, `rule`, `collect`, `end`, `custom`

## `risk_scenes.json`

### Purpose

Defines the list of all available risk scenes and their metadata.

### Structure

```json
{
  "version": "string",
  "generated_at": "string",
  "scenes": []
}
```

### Scene Object

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `scene_key` | string | yes | Stable scene identifier |
| `scene_name` | string | yes | Display name |
| `description` | string or null | yes | Short scene summary |
| `status` | string | yes | See enumerations |
| `scene_path` | string | yes | Relative path to scene folder |
| `entry_workflow_id` | string or null | yes | Main workflow identifier |
| `owners` | array | yes | Owning users or groups |
| `tags` | array | yes | Search and grouping tags |
| `created_at` | string or null | yes | ISO 8601 |
| `updated_at` | string or null | yes | ISO 8601 |

## `schemas/scenes/<scene_key>/workflow.json`

### Purpose

Defines workflow graph structure for one scene.

### Structure

```json
{
  "scene_key": "string",
  "workflow_id": "string",
  "workflow_name": "string",
  "entry_node_ids": [],
  "nodes": [],
  "edges": [],
  "metadata": {}
}
```

### Node Object

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `node_id` | string | yes | Stable node identifier |
| `node_type` | string | yes | See enumerations |
| `label` | string | yes | Display label |
| `enabled` | boolean | yes | Whether node is active |
| `position` | object | yes | Graph layout object |

### Position Object

| Field | Type | Required |
| --- | --- | --- |
| `x` | number | yes |
| `y` | number | yes |

### Edge Object

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `edge_id` | string | yes | Stable edge identifier |
| `source_node_id` | string | yes | Existing node reference |
| `target_node_id` | string | yes | Existing node reference |
| `order` | integer or null | yes | Branch order when applicable |
| `condition_ref` | string or null | no | Optional routing condition reference |

## `schemas/scenes/<scene_key>/nodes.json`

### Purpose

Defines node metadata and rule membership for one scene.

### Structure

```json
{
  "scene_key": "string",
  "nodes": []
}
```

### Node Definition

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `node_id` | string | yes | Must exist in `workflow.json` |
| `node_name` | string | yes | Human-readable node name |
| `node_type` | string | yes | See enumerations |
| `description` | string or null | yes | Optional business summary |
| `rule_refs` | array | yes | Ordered rule references |
| `next_node_ids` | array | yes | Optional navigation helper |
| `metadata` | object | yes | Extra scene-specific node data |

### Rule Reference

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `rule_id` | string | yes | Must exist in `rules.json` |
| `priority` | integer or null | yes | Rule order in node |
| `enabled` | boolean | yes | Whether the rule is active |

## `schemas/scenes/<scene_key>/rules.json`

### Purpose

Defines normalized rule logic for one scene.

### Structure

```json
{
  "scene_key": "string",
  "rules": []
}
```

### Rule Definition

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `rule_id` | string | yes | Stable rule identifier |
| `rule_name` | string | yes | Primary technical name |
| `rule_name_cn` | string or null | yes | Optional localized name |
| `status` | string | yes | See enumerations |
| `priority` | integer or null | yes | Scene-level rule priority |
| `hit_expression` | string | yes | Normalized hit logic |
| `assignment_expression` | string | yes | Normalized assignment logic |
| `action` | string | yes | `pass`, `review`, or `reject` |
| `reason_codes` | array | yes | Array of strings |
| `source` | object | yes | Source trace metadata |
| `metadata` | object | yes | Optional custom attributes |

### Source Object

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `source_system` | string or null | yes | Upstream system name |
| `source_file` | string or null | yes | Upstream file name or path |
| `source_row_id` | string, integer, or null | no | Row identifier when available |
| `mapping_method` | string or null | yes | `direct`, `derived`, `manual`, or similar |
| `raw_fragments` | array or object | no | Original tokens or fragments |

## `schemas/scenes/<scene_key>/variables.json`

### Purpose

Defines scene-private variables for one scene.

### Structure

```json
{
  "scene_key": "string",
  "variables": []
}
```

### Variable Definition

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `variable_key` | string | yes | Stable lookup key |
| `variable_name` | string | yes | Display name |
| `scope` | string | yes | `input` or `derived` |
| `data_type` | string | yes | `string`, `number`, `boolean`, `object`, `array`, or domain-specific value |
| `description` | string or null | yes | Business meaning |
| `source_path` | string or null | yes | Original source path such as `s.requestTime` |
| `default_value` | any | yes | Must be explicit |
| `examples` | array | yes | Example values |
| `searchable` | boolean | yes | Whether the field should be indexed in UI search |
| `metadata` | object | no | Optional custom attributes |

## `public_variables.json`

### Purpose

Defines shared variables used across multiple scenes.

### Structure

```json
{
  "version": "string",
  "variables": []
}
```

### Public Variable Definition

Use the same structure as scene-local variables, with these additional fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `scope` | string | yes | Must be `public` |
| `shared_by` | array | yes | Scene keys that reuse the variable |

## `history_data.json`

### Purpose

Defines normalized historical decision records.

### Structure

```json
{
  "version": "string",
  "records": []
}
```

### History Record

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `record_id` | string | yes | Stable history identifier |
| `scene_key` | string | yes | Must exist in `risk_scenes.json` |
| `user_id` | string or null | yes | User identifier |
| `event_time` | string or null | yes | ISO 8601 |
| `inputs` | object | yes | Normalized request payload |
| `derived_variables` | object | yes | Normalized derived payload |
| `hit_rules` | array | yes | Rule IDs or stable rule keys |
| `strategy_result` | string or null | yes | Final strategy value |
| `reason_codes` | array | yes | Must remain an array |
| `final_decision` | string or null | yes | Decision summary |
| `source` | object | yes | Source trace metadata |
| `raw_refs` | object | yes | Optional raw payload references |

## `user_labels.json`

### Purpose

Defines normalized user labels.

### Structure

```json
{
  "version": "string",
  "labels": []
}
```

### Label Record

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `user_id` | string | yes | User identifier |
| `label` | string | yes | Display label value |
| `label_type` | string or null | yes | Label category |
| `scene_key` | string or null | yes | Related scene when applicable |
| `applied_at` | string or null | yes | ISO 8601 |
| `source` | object | yes | Source trace metadata |
| `metadata` | object | yes | Optional custom attributes |

## Minimal Valid Package Checklist

A minimal valid package must satisfy all of the following:

- `risk_scenes.json` exists and contains at least one scene.
- Every `scene_key` in scene-local files exists in `risk_scenes.json`.
- Every node referenced by a workflow edge exists in `workflow.json`.
- Every `rule_ref.rule_id` in `nodes.json` exists in `rules.json`.
- Every `scene_key` in `history_data.json` exists in `risk_scenes.json`.
- Every top-level file is valid JSON.
- No file relies on implied defaults for required fields.

## Practical Mapping Notes

- Request payloads like `s` usually map to `inputs`.
- Derived payloads like `e` usually map to `derived_variables`.
- Decision payloads like `o` usually map to `strategy_result`, `final_decision`, and `reason_codes`.
- Workflow graph exports usually map to `workflow.json`.
- Node-to-rule mapping tables usually map to `nodes.json`.
- Rule detail token tables usually map to `rules.json`.

## Example Usage

Use [README.md](/Users/kc/Desktop/个人资料/个人项目/KittyChain/kittychain/rule_engine/README.md) for a complete example package.
