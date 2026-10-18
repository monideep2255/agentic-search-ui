"""Which third-party top-level modules does the `s3` client load?

Imports the CLI entry point and every sibling the CLI lazily imports when it
runs a real `ask` (credentials, client, render, sse), then lists the
non-stdlib top-level modules left in sys.modules. Run with the installed
prefix on PYTHONPATH so it measures the wheel, not the worktree.
"""
import importlib
import sys

before = set(sys.modules)
for name in (
    "system_03_search_agent.adapters.cli.main",
    "system_03_search_agent.adapters.cli.credentials",
    "system_03_search_agent.adapters.cli.client",
    "system_03_search_agent.adapters.cli.render",
    "system_03_search_agent.adapters.cli.sse",
):
    importlib.import_module(name)
after = set(sys.modules) - before
stdlib = set(sys.stdlib_module_names)
tops = sorted({m.split(".")[0] for m in after} - stdlib - {"_distutils_hack"})
print("module file:", sys.modules["system_03_search_agent.adapters.cli.main"].__file__.split("int_prefix")[-1])
print("third-party top-level modules loaded by the s3 client:")
for t in tops:
    print("  ", t)
first_party = sorted(m for m in after if m.startswith("system_03_search_agent"))
print("first-party modules loaded:", len(first_party))
for m in first_party:
    print("  ", m)
