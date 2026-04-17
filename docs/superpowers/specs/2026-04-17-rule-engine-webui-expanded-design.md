# Rule Engine Web UI Expanded Design

## Goal

Replace the current minimal read-only web entry with a structured rule engine product UI under `kittychain/rule_engine/webui`, and add replay batch persistence under `kittychain/rule_engine/schemas/replays/`.

This design keeps the existing Flask approach, but expands it into a multi-page product surface with navigation, search, pagination, detail modals, and persisted replay history.

## Scope

This design adds:

- a left-side navigation layout
- separate pages for home, scenes, public variables, history logs, and replays
- scene detail and node detail pages
- modal-based detail views for rules and compact history fields
- persisted replay batch JSON files under `kittychain/rule_engine/schemas/replays/`
- a replay list page and replay detail page

This design does not add:

- editing flows
- authentication
- API-first architecture
- database storage
- background replay workers

## Core Decisions

### Web Stack

- Keep Flask + Jinja.
- Keep server-rendered pages.
- Use small amounts of client-side JavaScript only for modal open/close behavior.

### Replay Persistence

- Persist replay batches as JSON files under `kittychain/rule_engine/schemas/replays/`.
- Treat replay batches as rule engine data artifacts, separate from static scene definitions but still stored inside the rule engine package tree.
- Each replay run produces one replay batch file.

### Search and Pagination

- Use server-side search and pagination.
- Default page size for variable and log tables: `20`.
- Search parameters stay in the query string so pages are shareable and refresh-safe.

## Information Architecture

The web UI should have a persistent left navigation with these entries:

- Home
- Scenes
- Public Variables
- History Logs
- Replays

## Pages

### Home

Route: `/`

The home page should only show summary information:

- scene count
- per-scene private variable counts
- public variable count
- history log count
- replay batch count

It should not embed full history tables or replay detail tables.

### Scenes List

Route: `/scenes`

This page should list all scenes with:

- scene key
- scene name
- status
- private variable count
- node count

Clicking a scene opens the scene detail page.

### Scene Detail

Route: `/scenes/<scene_key>`

This page should show:

- scene metadata
- workflow
- scene-private variable table

Scene-private variables must support:

- search by `variable_key`
- search by `variable_name`
- pagination with `20` rows per page

Workflow nodes should be interactive. Double-clicking a node should navigate to the corresponding node page.

### Node Detail

Route: `/nodes/<scene_key>/<node_id>`

This page should show:

- node metadata
- enabled rules in priority order

Each rule row must be clickable. Clicking a rule opens a modal with the full rule detail pulled from `rules.json` through the provider layer.

The modal should include at least:

- `rule_id`
- `rule_name`
- `rule_name_cn`
- `status`
- `priority`
- `action`
- `reason_codes`
- `hit_expression`
- `assignment_expression`

### Public Variables

Route: `/public-variables`

This page should only show public variables.

The table must include:

- `variable_key`
- `variable_name`

It must support:

- search by `variable_key`
- search by `variable_name`
- pagination with `20` rows per page

### History Logs

Route: `/history`

This page should list historical records with these columns:

- scene name
- `record_id`
- `user_id`
- `inputs`
- `derived_variables`
- `hit_rules`
- `strategy_result`
- `reason_codes`

Filtering must support:

- scene name dropdown
- exact `record_id`
- exact `user_id`
- fuzzy search across:
  - `inputs`
  - `derived_variables`
  - `hit_rules`
  - `strategy_result`
  - `reason_codes`

`inputs`, `derived_variables`, and `hit_rules` should render as compact previews in the table. Clicking them opens a modal with the full value.

### Replays List

Route: `/replays`

This page should show replay batch summaries.

Each batch row should include:

- `replay_id`
- `created_at`
- selected filters
- total records
- changed records
- unchanged records

The page should also provide a way to create a new replay batch using current filter inputs.

### Replay Detail

Route: `/replays/<replay_id>`

This page should show the records inside one persisted replay batch.

The row shape should be close to the history logs page, but scene name is not required because the replay batch filters already define scope.

Each row should expose:

- original history record fields needed for inspection
- replay result
- diff result

Compact fields should use the same modal pattern as the history logs page.

## Replay Batch File Format

Create one JSON file per replay batch:

- `kittychain/rule_engine/schemas/replays/<replay_id>.json`

Suggested top-level structure:

```json
{
  "replay_id": "replay_20260417_153000_register",
  "created_at": "2026-04-17T15:30:00Z",
  "filters": {
    "scene_key": "register",
    "user_id": null,
    "text": "review"
  },
  "summary": {
    "total_records": 100,
    "changed_records": 12,
    "unchanged_records": 88,
    "strategy_before": {},
    "strategy_after": {},
    "reason_codes_before": {},
    "reason_codes_after": {},
    "rule_hit_difference_counts": {}
  },
  "records": [
    {
      "record_id": "history_register_xxx",
      "scene_key": "register",
      "user_id": "user_123",
      "event_time": "2026-04-17T10:00:00Z",
      "inputs": {},
      "derived_variables": {},
      "hit_rules": [],
      "strategy_result": "accept",
      "reason_codes": [],
      "replay_result": {},
      "diff": {}
    }
  ]
}
```

The replay record payload can be normalized to avoid duplication, but the file must remain directly inspectable and sufficient to render the replay detail page without recomputing replay at read time.

## Provider Layer

The provider layer should be expanded into page-oriented providers:

- home summary provider
- scenes list provider
- scene detail provider
- node detail provider
- public variables provider
- history logs provider
- replay creation provider
- replay list provider
- replay detail provider

Providers must keep using existing rule engine helpers where possible:

- `query.py`
- `replay.py`
- `diff.py`

Replay persistence helpers can be added under `kittychain/rule_engine/` or `kittychain/rule_engine/webui/`, but they should remain small and JSON-first.

## UI Behavior

### Navigation

- The base layout should include a left sidebar and a content area.
- The active page should be visually indicated.

### Pagination

- Use `page` query parameters.
- Page size is fixed at `20` for this phase.

### Search

- Search inputs should round-trip through query parameters.
- Empty search values should not filter results.

### Modals

- Use lightweight modal markup with a small script.
- Do not add a frontend framework.
- The modal payload may be embedded in the page or rendered via hidden sections, as long as it stays simple.

## Validation Rules

- Missing scene, node, history record, or replay batch should return `404`.
- Replay batch write helpers must create the `schemas/replays/` directory if it does not exist.
- Replay batch files must be valid JSON and loadable without replay recomputation.

## Testing

Add or expand `tests/test_rule_engine_webui.py` to cover:

- sidebar navigation rendering
- home summary rendering
- scenes list page
- scene detail variable search
- scene detail variable pagination
- node detail rendering
- rule detail modal payload presence
- public variables search
- public variables pagination
- history log filters
- history modal payload rendering
- replay batch creation
- replay list rendering
- replay detail rendering
- missing replay batch 404

Add persistence-focused tests for replay batch JSON read/write behavior.

## Files To Add Or Modify

- Modify: `kittychain/rule_engine/webui/app.py`
- Modify: `kittychain/rule_engine/webui/views.py`
- Modify: `kittychain/rule_engine/webui/providers.py`
- Modify: `kittychain/rule_engine/webui/templates/base.html`
- Modify: existing page templates
- Create: scene list template if separated from scene detail
- Create: public variables template
- Create: history logs template
- Create: replays list template
- Create: replay detail template
- Create: lightweight modal script support
- Create or modify replay persistence helpers under `kittychain/rule_engine/`
- Create: `kittychain/rule_engine/schemas/replays/`
- Modify: `tests/test_rule_engine_webui.py`
- Add persistence tests as needed

## Out Of Scope

- editing schemas from the web UI
- authentication and multi-user isolation
- background replay jobs
- replacing JSON persistence with a database
- rich client-side graph editing

## Success Criteria

This expanded web UI is complete when:

- the app exposes the five top-level navigation pages
- scene, variable, history, and replay pages all support the requested search and pagination behavior
- node rule detail and history/replay detail use modal-based inspection
- replay batches are persisted under `kittychain/rule_engine/schemas/replays/`
- replay batches can be listed and opened later without recomputing the batch
- `python3 -m pytest -q` passes
- `python3 -m kittychain.rule_engine.webui.app` starts successfully
