# Rule Engine Simulations Design

## Goal

Extend the rule engine web UI so users can create persistent simulation scenes from existing source scenes, edit the copied workflow artifacts for those simulations, and run replays only against simulation scenes while sourcing replay targets from the original scene's history records.

## Scope

This design covers:

- Scene metadata changes required to distinguish source scenes from simulation scenes
- Persistent simulation creation from the Scenes page
- Editing simulation workflow, nodes, and rules
- Replay form and replay target filtering changes
- Test coverage needed to ship the feature safely

This design does not cover:

- Editing source scenes
- Variable editing
- Batch creation of multiple simulations at once
- Deleting simulations
- Renaming or re-parenting an existing simulation

## Current State

- Scenes are defined by `risk_scenes.json` plus one folder per scene under `schemas/scenes/<scene_key>/`
- The web UI renders scenes and replay pages from the loaded package and is currently read-only
- Replay creation accepts `scene_key`, `user_id`, and free-text search
- Replay filtering is based on `history_data.json`
- History records reference only the original scene key

## Chosen Approach

Treat a simulation as a normal scene with two extra metadata fields:

- `scene_kind`: `"source"` or `"simulation"`
- `source_scene_key`: `null` for source scenes, original scene key for simulations

Simulation scene files live in the same `schemas/scenes/<scene_key>/` tree as source scenes. Creating a simulation copies the source scene's `workflow.json`, `nodes.json`, `rules.json`, and `variables.json` into a new scene folder and appends a new scene entry to `risk_scenes.json`.

This keeps loading, rendering, and replay evaluation on one code path instead of splitting source scenes and simulations into separate storage systems.

## Data Model

### `RiskScene`

Add fields:

- `scene_kind: str`
- `source_scene_key: str | None`

Rules:

- Existing scenes without these fields load as `scene_kind="source"` and `source_scene_key=None` for compatibility
- A simulation must have `scene_kind="simulation"`
- A simulation must have a non-empty `source_scene_key`
- A source scene must not point at another source scene via `source_scene_key`

### `risk_scenes.json`

Each scene entry will include:

- `scene_kind`
- `source_scene_key`

Example semantics:

- Source scene: `{"scene_key": "register", "scene_kind": "source", "source_scene_key": null, ...}`
- Simulation scene: `{"scene_key": "register_sim_20260418_ab12", "scene_kind": "simulation", "source_scene_key": "register", ...}`

## Simulation Creation Flow

### Entry Point

Add an `Add Simulation` button on each source scene row in the `Scenes` table.

Simulation rows do not show this button.

### Server Flow

Add a POST route that:

1. Accepts a source scene key
2. Loads the source scene metadata and scene package
3. Generates a unique simulation scene key
4. Copies the source scene files into a new scene folder
5. Appends a simulation scene entry to `risk_scenes.json`
6. Redirects to the new simulation scene page

### Generated Metadata

The new simulation scene:

- Reuses the source scene name with a visible simulation suffix
- Uses `scene_kind="simulation"`
- Uses `source_scene_key=<original scene key>`
- Uses a scene path that points at the new copied directory
- Starts with status `active`

### File Copy Rules

Copy as-is:

- `workflow.json`
- `nodes.json`
- `rules.json`
- `variables.json`

The copied workflow content keeps the same internal node and rule IDs. The simulation is isolated by scene folder and scene key, so ID rewrites are not required for this feature.

## Scenes Page Changes

The page will render two cards:

### Scenes card

Shows only source scenes and keeps the current summary columns, with one added action column for `Add Simulation`.

### Simulations card

Shows only simulation scenes and includes:

- Scene key
- Scene name
- Source scene
- Status
- Variable count
- Node count

Simulation rows link to their scene detail pages.

## Simulation Editing

### Editable Surfaces

Only simulation scenes are editable.

Editable data:

- Workflow definition in `workflow.json`
- Node definitions in `nodes.json`
- Rule definitions in `rules.json`

Variables remain copied and visible, but are not part of this feature's edit scope.

### UI Behavior

Reuse the existing scene detail page and add edit controls only when `scene.scene_kind == "simulation"`.

Minimum editing model:

- Workflow tab supports saving the full workflow JSON payload
- Node detail page supports saving the selected node JSON payload
- Rule content is editable from the node detail page for rules referenced by that node

The implementation should stay simple and avoid building a brand-new visual editor. JSON textareas or structured form fields are acceptable as long as they persist valid data and keep the existing page usable.

### Save Rules

- Source scenes reject edit requests with a 400 or 403-style response
- Simulation edits write back only to that simulation's copied files
- After save, reload the updated scene package and render the latest content

### Validation

For this task, validation is limited to:

- Required JSON shape can still be loaded by the existing loader
- Target scene must be a simulation before save

If a submitted edit cannot be parsed or loaded, the page should render an error message and keep the user on the edit surface instead of partially writing inconsistent files.

## Replay Changes

### Replay Form

Update the Create Replay form to:

- Show only simulation scenes in the scene selector
- Remove the `All scenes` option
- Remove the `Search text` input
- Add `Record ID`
- Keep `User ID`

Both `Record ID` and `User ID` are exact-match filters.

### Replay Target Resolution

Replay runs against the selected simulation scene, but records are selected from the source scene's history.

Resolution steps:

1. User selects a simulation scene
2. The backend resolves its `source_scene_key`
3. History records are filtered where `history_record.scene_key == source_scene_key`
4. Optional exact filters apply for `record_id` and `user_id`
5. Matching record IDs are replayed using the simulation scene key

This preserves the real historical inputs while exercising the simulation workflow and rules.

### Replay Persistence

Saved replay batch metadata should include:

- Selected simulation `scene_key`
- Resolved `source_scene_key`
- `record_id`
- `user_id`

The previous free-text replay filter is removed from the replay batch payload and UI.

## Provider and Query Changes

Add helpers for:

- Separating source scenes from simulation scenes
- Looking up a simulation's source scene
- Filtering history records by `record_id`

Keep existing history filtering behavior intact for the history logs page unless directly needed for replay creation.

## Testing Strategy

Follow TDD for behavior changes.

### Loader and model tests

- Load source scenes with default compatibility values
- Load simulation scenes with explicit `scene_kind` and `source_scene_key`

### Simulation creation tests

- Creating a simulation copies all required files
- Creating a simulation appends a valid metadata record to `risk_scenes.json`
- New simulation appears in the simulations list and links back to the source scene

### Web UI tests

- Scenes page renders separate `Scenes` and `Simulations` cards
- Source rows show `Add Simulation`
- Simulation rows do not show `Add Simulation`
- Replay form only lists simulation scenes
- Replay form shows `Record ID` and `User ID`
- Replay form no longer shows `All scenes` or `Search text`

### Replay tests

- Replay creation accepts `scene_key`, `record_id`, and `user_id`
- Replay selection pulls history from the simulation's `source_scene_key`
- Replay execution still evaluates using the simulation scene key

### Edit tests

- Simulation workflow, node, and rule updates persist to copied files
- Source scene edit attempts are rejected

## Risks and Tradeoffs

### JSON editing instead of a full visual editor

This is the simplest way to ship editable simulations without inventing a second UI system. It is less polished than a custom editor, but it keeps scope contained and fits the existing file-based architecture.

### Scene ID reuse inside copied files

Keeping node and rule IDs unchanged avoids broad rewrites. This is safe as long as scene isolation remains folder-based and all lookups stay scoped by scene key.

### Replay provenance

Because simulations use source-scene history, replay batch metadata must retain both the simulation key and source scene key so users can understand what was evaluated and where the records came from.

## Success Criteria

The feature is complete when:

1. A user can create a persistent simulation from a source scene on the Scenes page
2. The new simulation appears in a separate Simulations card and is marked as a simulation in metadata
3. A user can edit the simulation's workflow, nodes, and rules without mutating the source scene
4. The Replay form only permits simulation scenes and filters targets by exact `record_id` and `user_id`
5. Replay records are selected from the source scene history and evaluated against the simulation scene
6. Relevant tests pass
