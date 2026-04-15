# Rule Engine Phase 2 Design

## Goal

Add a read-only query surface under `kittychain/rule_engine` for the standardized JSON package built in phase 1.

Phase 2 should make it easy to inspect scenes, workflows, nodes, rules, variables, and history records from Python code and from a minimal manual command-line entry point.

## Scope

This phase includes:

- Python query helpers in `kittychain/rule_engine/query.py`
- focused tests in `tests/test_rule_engine_query.py`
- a minimal read-only `main()` entry point inside `query.py`

This phase does not include:

- replay or diff logic
- UI files
- adapters
- write paths
- caching, indexing, or persistence

## Assumptions

- Phase 1 models, loader, and validator remain the source of truth for package loading and validation.
- Query helpers should operate on already-loaded dataclasses instead of raw JSON dictionaries.
- The command-line inspection path must not rely on a new `kittychain/rule_engine/__main__.py`.
- The smallest useful command-line surface is enough for manual inspection; it does not need to be a polished product CLI.

## Chosen Approach

Use a small function-based query module that loads the package once per command invocation and performs in-memory filtering over the phase 1 dataclasses.

The query layer should stay intentionally thin:

- no service classes
- no new wrapper models unless a test clearly needs one
- no normalization beyond what phase 1 already provides

The command-line entry point should live in `query.py` and support direct execution through:

- `python -m kittychain.rule_engine.query`
- `python kittychain/rule_engine/query.py`

This keeps the manual inspection path simple and satisfies the constraint that phase 2 must not add `kittychain/rule_engine/__main__.py`.

## Query Surface

`query.py` should expose small read-only helpers with explicit names.

### Scene and Workflow Queries

- `list_scenes(package=None) -> tuple[RiskScene, ...]`
- `get_scene_workflow(scene_key, package=None) -> WorkflowDefinition`

These support scene list pages and scene workflow inspection.

`list_scenes()` should return scenes in the same order as `risk_scenes.json`.

`get_scene_workflow()` should raise a clear `KeyError` when the scene does not exist. This is enough for phase 2 because tests only cover valid lookups and the CLI can catch the exception to print a short message.

## Node and Rule Queries

- `list_node_rules(scene_key, node_id, package=None) -> tuple[RuleDefinition, ...]`
- `get_rule(scene_key, rule_id, package=None) -> RuleDefinition`

`list_node_rules()` should:

- find the scene package
- find the node by `node_id`
- resolve its `rule_refs` against the scene rules
- return rules in node reference order

This order matters more than global rule priority because the node view should reflect the node definition first.

## Variable Queries

- `list_scene_variables(scene_key, package=None) -> tuple[VariableDefinition, ...]`
- `list_public_variables(package=None) -> tuple[VariableDefinition, ...]`

`list_scene_variables()` should return only scene-private variables from that scene package.

`list_public_variables()` should return the already-loaded global public variable definitions unchanged.

No additional grouping or indexing is needed in this phase.

## History Queries

- `filter_history(scene_key=None, user_id=None, text=None, package=None) -> tuple[HistoryRecord, ...]`

One history filter function is enough for phase 2.

`filter_history()` should support:

- filtering by exact `scene_key`
- filtering by exact `user_id`
- fuzzy text matching across:
  - `inputs`
  - `derived_variables`
  - `final_decision`

The fuzzy match should be a minimal case-insensitive substring search over a serialized text view of those fields. Phase 2 does not need field-specific indexes or expression-aware search.

This keeps the implementation small while still satisfying the product-facing use cases in `PLAN.md`.

## CLI Surface

The command-line entry point in `query.py` should be intentionally small.

Supported behaviors:

- no arguments: print a summary with scene count, public variable count, and history record count
- `--scene <scene_key>`: print a scene summary and workflow ID
- `--user-id <user_id>`: print matching history record count
- `--text <value>`: print matching history record count

Combined filters should be allowed for history lookup, for example:

- `python -m kittychain.rule_engine.query --scene register --user-id user_001`
- `python -m kittychain.rule_engine.query --scene register --text review`

The CLI should print compact human-readable output only. It should not output JSON in this phase.

## Error Handling

Phase 2 should keep error handling minimal and explicit.

- Python helpers may raise `KeyError` for missing scenes, nodes, or rules.
- The CLI should catch those lookup errors and print a single-line message, then return a non-zero exit code.
- Invalid argument combinations do not need custom validation beyond what `argparse` already provides.

## Testing Strategy

Add `tests/test_rule_engine_query.py` with TDD coverage for exactly the phase 2 behaviors:

- listing scenes
- reading one workflow
- listing node rules by node ID
- reading one rule
- listing scene-private variables
- listing public variables
- filtering history by scene
- filtering history by user ID
- filtering history by fuzzy match on inputs
- filtering history by fuzzy match on derived variables
- filtering history by fuzzy match on decision output
- module and script `main()` smoke coverage for the minimal CLI

Tests should continue using the existing sample package under `kittychain/rule_engine/schemas`.

## File Changes

- Create `kittychain/rule_engine/query.py`
- Create `tests/test_rule_engine_query.py`
- Modify `kittychain/rule_engine/__init__.py` only if exporting query helpers provides value without widening scope

## Non-Goals

- No replay preparation types
- No query result pagination
- No sorting configuration
- No custom exceptions hierarchy
- No query object abstraction
- No package-level cached singleton

## Success Criteria

Phase 2 is complete when:

- focused query tests pass
- the query module can be executed directly without errors
- the query surface is small, read-only, and entirely backed by phase 1 dataclasses
- no new `__main__.py` file is added under `kittychain/rule_engine`
