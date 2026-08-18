"""The GraphQL delivery surface: build phase 4.3, `tracker/phase_4.3.md`.

Deliberately empty of re-exports. Each sibling module in this package
(types, fold, context, security, schema, router) is written and unit-tested
independently against the fixed interfaces `tracker/phase_4.3.md` names
before dispatch, and several of them (schema.py, router.py) do not exist
yet at the point this file is created. Re-exporting from here would make
this file's own import order a hidden dependency between modules that are
supposed to compose only through the fixed interfaces, so a caller imports
each sibling module directly (`system_03_search_agent.adapters.graphql.
types`, `...fold`, and so on) rather than through this package's namespace.
"""
