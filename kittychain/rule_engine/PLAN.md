# Lightweight Rule Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight rule engine under `kittychain/rule_engine` with a stable JSON standard, validation layer, read-only query surface, and a clear path to future adapter and UI workflows.

**Architecture:** The implementation should start from schema-first domain modeling. Standard JSON files are the source of truth, Python loaders and validators sit on top of them, and read-only services expose scene, node, rule, variable, and history views. UI and adapters should be built only after the standard package and validation logic are stable.

**Tech Stack:** Python, JSON, pytest, existing KittyChain package structure

---

## Scope Summary

This plan is intentionally phased.

- Phase 1 builds the standard, sample data package, loader, and validator.
- Phase 2 adds read-only query services for scenes, workflows, nodes, rules, variables, and history.
- Phase 3 adds the read-only product pages.
- Phase 4 adds edit and create flows.
- Phase 5 integrates adapter workflows and subagent handoff.

## Proposed File Structure

### Documentation and Standard Data

- Create: `kittychain/rule_engine/README.md`
- Create: `kittychain/rule_engine/SCHEMA_TEMPLATE.md`
- Create: `kittychain/rule_engine/ADAPTER_CONTRACT.md`
- Create: `kittychain/rule_engine/PLAN.md`
- Create: `kittychain/rule_engine/schemas/risk_scenes.json`
- Create: `kittychain/rule_engine/schemas/public_variables.json`
- Create: `kittychain/rule_engine/schemas/user_labels.json`
- Create: `kittychain/rule_engine/schemas/history_data.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/workflow.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/nodes.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/rules.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/variables.json`

### Python Engine and Validation

- Create: `kittychain/rule_engine/__init__.py`
- Create: `kittychain/rule_engine/models.py`
- Create: `kittychain/rule_engine/loader.py`
- Create: `kittychain/rule_engine/validator.py`
- Create: `kittychain/rule_engine/query.py`
- Create: `tests/test_rule_engine_loader.py`
- Create: `tests/test_rule_engine_validator.py`
- Create: `tests/test_rule_engine_query.py`

### Future UI

- Create later: UI files for home page, scene page, node page, rule modal, public variables page, and history logs page once the app surface is selected

## Phase 1: Standard Package Foundation

### Task 1: Create the rule engine package skeleton

**Files:**
- Create: `kittychain/rule_engine/__init__.py`
- Create: `kittychain/rule_engine/schemas/.gitkeep`
- Create: `kittychain/rule_engine/schemas/scenes/.gitkeep`

- [ ] Create the package directory and import boundary.
- [ ] Add empty schema directories so the standard package has a stable home.
- [ ] Verify the package can be imported without side effects.

**Verify:**
- Run: `python -c "import kittychain.rule_engine; print('ok')"`
- Expected: `ok`

### Task 2: Add standard sample JSON files

**Files:**
- Create: `kittychain/rule_engine/schemas/risk_scenes.json`
- Create: `kittychain/rule_engine/schemas/public_variables.json`
- Create: `kittychain/rule_engine/schemas/user_labels.json`
- Create: `kittychain/rule_engine/schemas/history_data.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/workflow.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/nodes.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/rules.json`
- Create: `kittychain/rule_engine/schemas/scenes/register/variables.json`

- [ ] Add one minimal but internally consistent sample package.
- [ ] Ensure all cross-file references resolve correctly.
- [ ] Keep the sample small enough to be readable and useful in tests.

**Verify:**
- Run: `python -m json.tool kittychain/rule_engine/schemas/risk_scenes.json >/dev/null`
- Run: `python -m json.tool kittychain/rule_engine/schemas/scenes/register/workflow.json >/dev/null`
- Expected: all sample files parse as valid JSON

### Task 3: Define Python domain models

**Files:**
- Create: `kittychain/rule_engine/models.py`
- Test: `tests/test_rule_engine_loader.py`

- [ ] Define small explicit dataclasses or typed structures for:
- [ ] `RiskScene`
- [ ] `WorkflowNode`
- [ ] `WorkflowEdge`
- [ ] `SceneNode`
- [ ] `RuleDefinition`
- [ ] `VariableDefinition`
- [ ] `HistoryRecord`
- [ ] `UserLabel`
- [ ] Keep fields aligned with `SCHEMA_TEMPLATE.md`.

**Verify:**
- Run targeted tests once the first loader test exists.

### Task 4: Implement loader functions

**Files:**
- Create: `kittychain/rule_engine/loader.py`
- Test: `tests/test_rule_engine_loader.py`

- [ ] Write failing tests for loading the sample package.
- [ ] Implement minimal JSON reading helpers.
- [ ] Implement loaders for:
- [ ] global package files
- [ ] one scene package
- [ ] all scenes from `risk_scenes.json`
- [ ] Return typed objects rather than loose dictionaries.

**Verify:**
- Run: `python -m pytest -q tests/test_rule_engine_loader.py`
- Expected: PASS

### Task 5: Implement validation rules

**Files:**
- Create: `kittychain/rule_engine/validator.py`
- Test: `tests/test_rule_engine_validator.py`

- [ ] Write failing tests for missing scene references, missing node references, and missing rule references.
- [ ] Implement structural validation and cross-file reference validation.
- [ ] Return explicit validation errors instead of raising vague exceptions.

**Verify:**
- Run: `python -m pytest -q tests/test_rule_engine_validator.py`
- Expected: PASS

## Phase 2: Read-Only Query Surface

### Task 6: Add query helpers for product views

**Files:**
- Create: `kittychain/rule_engine/query.py`
- Test: `tests/test_rule_engine_query.py`

- [ ] Write failing tests for:
- [ ] listing scenes
- [ ] reading one workflow
- [ ] listing node rules by node ID
- [ ] reading one rule
- [ ] listing scene-private variables
- [ ] listing public variables
- [ ] filtering history by scene
- [ ] filtering history by user ID
- [ ] filtering history by fuzzy match on inputs
- [ ] filtering history by fuzzy match on derived variables
- [ ] filtering history by fuzzy match on decision output
- [ ] Implement the smallest query helpers needed to satisfy those tests.

**Verify:**
- Run: `python -m pytest -q tests/test_rule_engine_query.py`
- Expected: PASS

### Task 7: Expose a simple manual inspection entry point

**Files:**
- Modify: `kittychain/rule_engine/query.py`
- Optional create: `kittychain/rule_engine/__main__.py`

- [ ] Add a small manual entry point for local inspection of scenes and history filters.
- [ ] Keep this read-only and minimal.

**Verify:**
- Run: `python -m kittychain.rule_engine`
- Expected: a basic summary or help output without errors

## Phase 3: Read-Only Product Surface

### Task 8: Implement home page data providers

**Files:**
- Create or modify UI-facing modules after the frontend entry point is confirmed

- [ ] Add providers for:
- [ ] scene list
- [ ] public variables list
- [ ] history filters and result listing
- [ ] Keep page logic dependent on query helpers, not raw JSON parsing.

**Verify:**
- Read-only page checks should show consistent counts with query-layer tests.

### Task 9: Implement scene page and node page data providers

**Files:**
- Create or modify scene and node view modules after frontend structure is confirmed

- [ ] Add scene workflow tab support from `workflow.json`.
- [ ] Add scene variables tab support from `variables.json`.
- [ ] Add node page support from `nodes.json`.
- [ ] Add rule detail modal support from `rules.json`.

**Verify:**
- Page data should render one scene package end-to-end from the sample schema package.

## Phase 4: Editing and Creation

### Task 10: Add schema-safe write services

**Files:**
- Create future write service modules under `kittychain/rule_engine/`
- Create tests for create and update flows

- [ ] Add explicit create and update operations for:
- [ ] scenes
- [ ] workflows
- [ ] nodes
- [ ] rules
- [ ] variables
- [ ] Ensure writes preserve cross-file consistency.
- [ ] Re-run validation after every write operation.

**Verify:**
- Mutation tests should confirm the package still validates after edits.

## Phase 5: Adapter Workflow Integration

### Task 11: Add adapter handoff surface

**Files:**
- Create future adapter-facing service modules under `kittychain/rule_engine/`
- Add tests for package generation and validation handoff

- [ ] Define one adapter entry contract that accepts user-provided files and a target output directory.
- [ ] Require adapter output to match `SCHEMA_TEMPLATE.md`.
- [ ] Require adapter behavior to match `ADAPTER_CONTRACT.md`.
- [ ] Add a validation gate so adapter output cannot be accepted silently when references are broken.

**Verify:**
- Adapter integration tests should fail on ambiguous or invalid package output and pass on a valid normalized package.

## Cross-Cutting Requirements

- All new behavior should be test-driven.
- Keep functions small and explicit.
- Avoid speculative abstractions until at least two real call sites exist.
- Use the JSON package as the only source of truth.
- Do not let UI or adapters bypass loader and validator logic.

## Final Verification

Before claiming phase completion, run:

- `python -m pytest -q`

Expected:

- Full test suite passes.

## Execution Notes

- Start with Phase 1 only.
- Do not begin UI work before sample JSON, loader, and validator are stable.
- Do not begin adapter work before schema and validation behavior are stable.
- If future requirements split this into separate frontend and backend projects, keep `rule_engine` as the backend contract source.
