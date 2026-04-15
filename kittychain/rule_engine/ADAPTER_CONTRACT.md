# Adapter Contract

## Purpose

This document defines how an adapter must behave when converting user-provided source files into the standard rule engine package.

The adapter target format is defined in [SCHEMA_TEMPLATE.md](/Users/kc/Desktop/个人资料/个人项目/KittyChain/kittychain/rule_engine/SCHEMA_TEMPLATE.md).

This document is normative for future adapter subagents.

## Priority Rule

If the user input is ambiguous, incomplete, contradictory, or open to multiple plausible interpretations, the adapter must ask the user for clarification.

The adapter must not silently choose a business interpretation.

Unless the user explicitly asks for source trace fields in the standardized JSON, the adapter must not include raw source file metadata such as `source_file`, `source_row_id`, or similar file-level provenance fields in the package output.

This rule has higher priority than speed, convenience, or partial completion.

## Mandatory Behavior

### 1. Ask Instead of Guessing

The adapter must ask the user before proceeding when any of the following is true:

- one source field could map to multiple standard fields
- multiple files disagree on scene identity, rule identity, node identity, or variable meaning
- one source dataset may represent one scene or many scenes and the boundary is unclear
- rule logic is incomplete and more than one normalized expression would be reasonable
- a value could be either an input variable or a derived variable
- strategy result and reason code sources conflict
- timestamps, IDs, or labels cannot be mapped deterministically

The adapter may only infer low-risk mechanical details, such as:

- filename normalization
- deterministic ID formatting from already stable source identifiers
- obvious direct field copies where meaning is unambiguous

The adapter must never infer business meaning without user confirmation.

### 2. Produce a Complete Standard Package

The adapter must output the full standard package for the requested scope.

Required output set:

- `risk_scenes.json`
- `public_variables.json`
- `user_labels.json`
- `history_data.json`
- `schemas/scenes/<scene_key>/workflow.json`
- `schemas/scenes/<scene_key>/nodes.json`
- `schemas/scenes/<scene_key>/rules.json`
- `schemas/scenes/<scene_key>/variables.json`

If a source dataset is missing, the adapter must still create the file with a valid empty structure when the package requires it.

### 3. Preserve Meaning Over Shape

The adapter must preserve business meaning before preserving raw source structure.

Examples:

- request payloads should map to `inputs`, even if the source uses a generic payload container
- derived results should map to `derived_variables`, even if they are stored in a flat export
- decision outputs should map to `strategy_result`, `final_decision`, and `reason_codes`, even if the source represents them across multiple columns

### 4. Preserve Stable IDs

When a stable source ID exists, the adapter must preserve it.

If the source does not provide a stable ID, the adapter may generate a deterministic ID from stable fields. The adapter must not generate random IDs.

### 5. Preserve Traceability

The adapter should preserve traceability in its implementation notes or response summary whenever possible, but should not emit raw source file provenance fields into the standardized JSON package unless the user explicitly requests them.

Recommended trace fields:

- `source_system`
- `source_file`
- `source_row_id`
- `mapping_method`
- `raw_fragments`

The adapter response should still make it possible to explain where a field came from.

### 6. Do Not Invent Rule Logic

The adapter must not create rule logic that does not exist in the source material.

If the source only contains partial rule fragments:

- preserve available fragments in `source.raw_fragments`
- normalize only what is directly supported
- ask the user if multiple rule interpretations are possible

### 7. Separate Concerns Correctly

The adapter must place information into the correct file:

- workflow graph structure belongs in `workflow.json`
- node metadata and rule membership belong in `nodes.json`
- rule logic belongs in `rules.json`
- scene-private variables belong in `variables.json`
- shared variables belong in `public_variables.json`
- historical execution records belong in `history_data.json`
- labels belong in `user_labels.json`

The adapter must not duplicate the same business concept across files unless the schema explicitly requires it.

### 8. Use Explicit Empty Values

Missing values must be represented explicitly:

- use `null` for unknown scalar values
- use `[]` for unknown repeated collections
- use `{}` for unknown object payloads

The adapter must not use placeholder strings such as:

- `"unknown"`
- `"tbd"`
- `"-"`

unless the source itself uses them and the value is intentionally preserved as raw content.

### 9. Prefer Validation Failure Over Silent Corruption

The adapter output must be considered invalid if:

- a referenced `scene_key` does not exist
- a workflow edge points to a missing node
- a `rule_ref.rule_id` points to a missing rule
- a history record references an unknown scene
- output JSON is structurally valid but semantically contradictory

If validation fails, the adapter must report the failure clearly instead of silently dropping data.

## Recommended Adapter Workflow

1. Inspect user-provided files and identify candidate scene boundaries.
2. Identify whether the files clearly map to:
- workflow data
- node and rule mapping data
- rule detail data
- variable definitions
- history data
- labels
3. Stop and ask the user if any mapping boundary is ambiguous.
4. Normalize the source into the standard package.
5. Validate cross-file references.
6. Report what was mapped directly, what was normalized, and what required user clarification.

## Adapter Output Expectations

An adapter response should make these points clear:

- what source files were used
- what `scene_key` values were created
- which mappings were direct
- which values were normalized
- whether any fields remain null because the source did not provide enough information
- whether the package passed validation

## Non-Goals

The adapter is not responsible for:

- redesigning the schema
- inventing missing business rules
- choosing between multiple business interpretations without user input
- hiding uncertainty

## Short Checklist For Adapter Subagents

- Did I preserve stable source IDs where possible?
- Did I avoid guessing business meaning?
- Did I ask the user about every meaningful ambiguity?
- Did I generate the complete standard package?
- Did I keep workflow, nodes, rules, variables, history, and labels separate?
- Did I avoid writing raw source file trace fields into the standardized JSON unless the user explicitly asked for them?
- Did I validate all cross-file references?

If any answer is no, the adapter should not claim completion.
