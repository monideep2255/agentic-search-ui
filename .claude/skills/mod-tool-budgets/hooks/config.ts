// Per-repository settings for mod-tool-budgets.
//
// The mod reads the per tool timeout table in the budgets rule and the timeout
// a tool declares in its own source. It checks that the two numbers agree. It
// does not check that the code enforces the timeout at run time.

export const config = {
  // Source of the table: a markdown table whose first column is the tool name
  // and whose second column holds the timeout in seconds.
  rulePath: '.claude/rules/tool-call-budgets.md',

  // An edit to a file matching these globs triggers the check.
  // The kit's glob needs a folder between ** and the file name, so the top level is listed too.
  toolGlobs: ['src/system_03_search_agent/tools/*.py', 'src/system_03_search_agent/tools/**/*.py'] as string[],

  // An edit to this file re-checks every tool in the table, since the shared budget changed.
  budgetModule: 'src/system_03_search_agent/harness/call_budget.py',

  // Folder holding one source file per tool, named <tool>.py after the table's first column.
  toolsDir: 'src/system_03_search_agent/tools',

  // A top level constant counts as a declared timeout when its name matches this.
  // Other budget constants, such as a sub step enrichment budget, are not the tool's timeout.
  timeoutName: /^[A-Z_][A-Z0-9_]*(?:TIMEOUT|TOTAL_BUDGET)[A-Z0-9_]*$/,

  // Shared files that hold a timeout constant a tool imports by name.
  constantFiles: ['src/system_03_search_agent/tools/graph_schema_constants.py'] as string[],

  // A tool that routes every call through a shared transport inherits that transport's default timeout.
  // The marker is matched in the tool's source. The first delegate whose marker matches is used.
  delegates: [
    { marker: /\bncbi_transport\b/, file: 'src/system_03_search_agent/tools/ncbi_transport.py' },
  ] as { marker: RegExp; file: string }[],

  // A table timeout cell matching this is marked unsettled: a mismatch is informational only.
  unsettled: /provisional|unconfirmed|not settled|unsettled|to be confirmed/i,
}
