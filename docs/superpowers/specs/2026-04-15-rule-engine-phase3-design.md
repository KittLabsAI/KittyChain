# Rule Engine Phase 3 Design

## Goal

Add offline replay and diff analysis for the rule engine so that current rule definitions can be re-run against historical records and compared with previously stored outcomes.

Phase 3 should produce a reusable replay foundation for multiple scenes, not just a single hard-coded sample path.

## Scope

This phase includes:

- a dedicated expression evaluator in `kittychain/rule_engine/evaluator.py`
- replay orchestration in `kittychain/rule_engine/replay.py`
- diff and summary helpers in `kittychain/rule_engine/diff.py`
- focused tests in `tests/test_rule_engine_evaluator.py` and `tests/test_rule_engine_replay.py`
- a minimal read-only manual replay entry point without creating `kittychain/rule_engine/__main__.py`

This phase does not include:

- persistence
- background jobs
- UI files
- adapters
- write-back into the schema package
- a fully generic business rules platform

## Assumptions

- Phase 1 remains the source of truth for package loading and validation.
- Phase 2 remains the source of truth for history selection and read-only queries.
- Replay should reuse the existing standardized JSON files and dataclasses rather than introduce a second package format.
- Unsupported operators or functions must be surfaced explicitly instead of being silently treated as non-matches.
- The command-line entry point must continue to avoid a new `kittychain/rule_engine/__main__.py`.

## Chosen Approach

Use three focused modules with clear responsibilities:

- `evaluator.py` handles expression evaluation and assignment application
- `replay.py` handles single-record and batch replay orchestration
- `diff.py` handles comparison and aggregate reporting

This is intentionally more structured than Phase 2 because replay has two distinct concerns:

- evaluating expressions against a runtime context
- comparing replayed outputs against stored historical outputs

Keeping those concerns separate avoids growing `replay.py` into a large mixed-responsibility module.

## Module Responsibilities

### `evaluator.py`

`evaluator.py` should own the expression language runtime.

It should provide small explicit helpers such as:

- `evaluate_expression(expression, context) -> EvaluationResult`
- `apply_assignments(assignments, context) -> dict[str, object]`

The evaluator should understand the current normalized JSON rule format rather than raw source-system strings.

Supported expression forms in this phase:

- atomic comparisons with:
  - `=`
  - `!=`
  - `>`
  - `>=`
  - `<`
  - `<=`
  - `in`
  - `not in`
  - `exist`
  - `not exist`
  - `is true`
  - `is false`
  - `start with`
- boolean composition with:
  - `and`
  - `or`
- variable references with string names
- function operands expressed as nested objects

Supported assignment form in this phase:

- `{"var": "<name>", "operator": "set", "value": <value>}`

No other assignment operators should be added unless the real sample package requires them.

### `replay.py`

`replay.py` should own replay orchestration and result assembly.

It should provide:

- replay dataclasses
- `replay_record(record, package) -> ReplayResult`
- `replay_records(scene_key=None, user_id=None, record_ids=None, package=None) -> tuple[ReplayResult, ...]`
- summary helpers or wrappers that call into `diff.py`

`replay.py` should:

- build the runtime context from `inputs` and `derived_variables`
- evaluate scene rules against that context
- apply assignments from hit rules
- produce replayed values for:
  - `hit_rules`
  - `reason_codes`
  - `strategy_result`
  - `final_decision`
- carry explicit issue metadata when replay is partial or unsupported

### `diff.py`

`diff.py` should stay comparison-focused.

It should provide:

- field-level diff structures
- `diff_replay_result(record, replay_result) -> ReplayDiff`
- aggregate summary helpers over many replay results

This module should not evaluate expressions or select records.

## Runtime Context Model

Replay should use one mutable in-memory context per record.

The initial context is:

- all `record.inputs`
- then all `record.derived_variables`

When a rule hits, `assignment_expression` updates the replay context so later rules observe the new values.

The original `HistoryRecord` must remain unchanged.

## Function Handling

The evaluator should use a whitelist dispatcher for known functions found in the standardized package.

The first phase of support should include only functions already seen in the sample data, such as:

- `获取对象属性`
- `获取邮箱后缀`
- `解密函数`

If a new function appears and is not supported, the evaluator must not guess.

## Unsupported Behavior Policy

Phase 3 uses a strict-but-nonfatal unsupported policy.

If a rule contains an unsupported function or operator:

- record a structured issue such as `unsupported_function` or `unsupported_operator`
- mark the affected rule evaluation as unsupported
- continue replaying the rest of the record
- surface the unsupported state in the single-record result
- count unsupported rules and records in aggregate summaries

This means replay continues, but unsupported behavior is visible and never silently downgraded into a clean non-match.

## Evaluation Semantics

Replay should be deterministic and offline.

That means:

- no network calls
- no time-dependent implicit behavior beyond the values already present in the record
- no writes back to the package
- no external service lookup

When a function needs data not available in the historical record, the evaluator should surface an explicit issue rather than synthesize business meaning.

## Replay Output Model

Phase 3 should introduce explicit replay result models, most likely in `models.py`, for example:

- `ReplayIssue`
- `EvaluationResult`
- `ReplayResult`
- `FieldDiff`
- `ReplayDiff`
- `ReplaySummary`

The exact file placement can stay flexible, but the model names and fields should be stable and typed.

At minimum, `ReplayResult` should capture:

- `record_id`
- `scene_key`
- replayed `hit_rules`
- replayed `reason_codes`
- replayed `strategy_result`
- replayed `final_decision`
- `issues`
- whether the record is `changed`

At minimum, `ReplaySummary` should capture:

- total replayed records
- changed count
- unchanged count
- unsupported record count
- distributions for strategy result before and after replay
- distributions for reason codes before and after replay

## Diff Behavior

Diff logic should compare stored historical outputs against replayed outputs for:

- `hit_rules`
- `reason_codes`
- `strategy_result`
- `final_decision`

The comparison should be explicit and field-based, not stringified whole-object comparisons.

Each replayed record should be clearly classified as:

- unchanged
- changed
- changed with unsupported issues

## CLI Surface

The manual replay entry point should remain minimal and read-only.

Acceptable implementations:

- add replay flags to `query.py`
- or add a `main()` in `replay.py`

Unacceptable implementation:

- adding `kittychain/rule_engine/__main__.py`

The CLI only needs enough surface for local inspection, such as:

- replay one scene
- replay one user
- replay one explicit record
- print counts for changed, unchanged, and unsupported

The CLI should print compact human-readable output only.

## Testing Strategy

Phase 3 should have two complementary test files.

### `tests/test_rule_engine_evaluator.py`

This file should cover:

- atomic operator behavior
- boolean composition behavior
- supported function dispatch
- assignment application
- unsupported operator behavior
- unsupported function behavior

These tests should be small and unit-level so evaluator failures are easy to localize.

### `tests/test_rule_engine_replay.py`

This file should cover:

- replay result dataclasses
- replaying one history record
- replaying a filtered batch of records
- diff comparison against stored history
- changed versus unchanged classification
- unsupported issue propagation
- aggregate summary calculation
- module or script `main()` smoke coverage for manual replay inspection

Tests should continue using the sample package under `kittychain/rule_engine/schemas`.

## File Changes

- Create `kittychain/rule_engine/evaluator.py`
- Create `kittychain/rule_engine/replay.py`
- Create `kittychain/rule_engine/diff.py`
- Modify `kittychain/rule_engine/models.py`
- Optional modify `kittychain/rule_engine/query.py` if the manual replay entry point is attached there
- Create `tests/test_rule_engine_evaluator.py`
- Create `tests/test_rule_engine_replay.py`

## Non-Goals

- No background execution queue
- No persistence model for replay jobs
- No generic plugin architecture for arbitrary functions
- No business-logic guessing when data is incomplete
- No automatic backfill into `history_data.json`
- No UI workflow for replay results

## Success Criteria

Phase 3 is complete when:

- evaluator unit tests pass
- replay and diff tests pass
- unsupported operators and functions are surfaced explicitly
- replay works for filtered historical records without mutating the source package
- manual replay inspection runs without adding `kittychain/rule_engine/__main__.py`
