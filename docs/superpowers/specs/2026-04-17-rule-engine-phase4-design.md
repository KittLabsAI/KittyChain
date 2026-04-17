# Rule Engine Phase 4 Design

## Goal

Add a real, locally accessible, read-only product surface for the rule engine using Flask under `kittychain/rule_engine/webui`.

The phase 4 deliverable is a standalone Web entry point for browsing the current rule engine package. It must not be coupled to the existing `kittychain` CLI flow.

## Scope

Phase 4 adds:

- a Flask-based `webui` package under `kittychain/rule_engine/`
- server-rendered read-only pages
- small UI-facing provider helpers that reuse the existing query, replay, and diff layers
- focused tests for the web entry point and page rendering

Phase 4 does not add:

- edit or create flows
- authentication or permissions
- persistence, caching, or background jobs
- a frontend build pipeline
- coupling to the existing `kittychain` CLI entry points

## Constraints

- The Web surface must stay read-only.
- Page data must come from `query.py`, `replay.py`, and `diff.py`, not from direct JSON parsing in the view layer.
- The entry point must be runnable directly, for example:
  - `python3 -m kittychain.rule_engine.webui.app`
- The implementation should introduce Flask as the only new framework dependency for this phase.

## Recommended Structure

Use a small Flask package layout:

- `kittychain/rule_engine/webui/__init__.py`
- `kittychain/rule_engine/webui/app.py`
- `kittychain/rule_engine/webui/views.py`
- `kittychain/rule_engine/webui/providers.py`
- `kittychain/rule_engine/webui/templates/`
- `tests/test_rule_engine_webui.py`

This keeps the first web surface simple while leaving a clear place for future page growth.

## Routing Model

### Home Page

Route: `/`

The home page should show:

- scene list
- public variables list
- a small history filter form
- filtered history results
- replay summary for the selected scene, or a default summary when a scene is selected by query string

Expected inputs:

- optional `scene`
- optional `user_id`
- optional `text`

The page should remain usable even with no filters applied.

### Scene Page

Route: `/scenes/<scene_key>`

The scene page should show:

- scene metadata
- workflow edges and nodes from the loaded scene package
- scene-private variables
- node list with links to node detail pages

This page is the main read-only entry for understanding one scene package end to end.

### Node Page

Route: `/nodes/<scene_key>/<node_id>`

The node page should show:

- node metadata
- enabled rules for the node in priority order
- basic rule details inline

No modal implementation is required in phase 4. A simple inline presentation is enough.

### History Detail Page

Route: `/history/<record_id>`

The history detail page should show:

- the historical record
- the current replay result
- the field-level diff result

This page is the main way to inspect one record end to end from stored history through current replay behavior.

## Provider Layer

The provider layer should be thin and explicit.

Suggested responsibilities:

- home page data assembly
- scene page data assembly
- node page data assembly
- history detail data assembly

Providers should reuse:

- `query.py` for scene, node, variable, and history lookups
- `replay.py` for replaying one historical record
- `diff.py` for computing diffs and summaries

Providers should return plain dictionaries or small typed structures that are convenient for Jinja templates. They should not duplicate business logic already present in the rule engine layers.

## Template Strategy

Use Flask + Jinja server-rendered templates only.

Keep the HTML straightforward:

- one shared base template
- one template per page
- simple tables and sections
- links between home, scene, node, and history pages

The goal is inspectability, not polished product design. Phase 4 should be easy to extend later without introducing client-side complexity now.

## Error Handling

Keep error handling minimal and explicit:

- unknown scene key -> 404 page
- unknown node ID within a valid scene -> 404 page
- unknown history record ID -> 404 page

Do not add a custom global error framework. Standard Flask behavior with a small template or plain response is enough.

## Testing

Add `tests/test_rule_engine_webui.py` with Flask test client coverage for:

- home page renders and includes scene data
- home page filter query parameters affect history results
- scene page renders one known scene
- node page renders one known node with enabled rules
- history detail page renders replay and diff data
- missing scene, node, and history record return 404

Tests should focus on stable page content and route behavior, not pixel-level HTML details.

## Files To Modify

- Add `Flask` to `pyproject.toml`
- Create `kittychain/rule_engine/webui/__init__.py`
- Create `kittychain/rule_engine/webui/app.py`
- Create `kittychain/rule_engine/webui/views.py`
- Create `kittychain/rule_engine/webui/providers.py`
- Create Jinja templates under `kittychain/rule_engine/webui/templates/`
- Create `tests/test_rule_engine_webui.py`

## Verification

Phase 4 should be considered complete when:

- `python3 -m pytest -q tests/test_rule_engine_webui.py` passes
- `python3 -m pytest -q` passes
- `python3 -m kittychain.rule_engine.webui.app` starts a local Flask server without errors
- the browser can load the home page and navigate to scene, node, and history detail pages

## Out Of Scope

The following are intentionally deferred:

- page editing
- create flows
- rule detail modals with richer interactivity
- adapter upload or generation flows
- API-first design
- background replay jobs

Phase 4 is successful if it gives the project a real, local, read-only web entry point on top of the existing rule engine package.
