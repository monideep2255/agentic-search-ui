// Per-repository settings for mod-test-triple.
//
// The check is a name based heuristic. It looks for a test file that mentions
// the route path, then for test function names that suggest a valid, an
// invalid, and an empty input case. It cannot tell whether a test named
// "invalid" really sends invalid input, and it cannot see a case written
// under a name that matches none of these words.

export const config = {
  // Files edited under this folder have their new text scanned for routes.
  adapterDir: 'src/system_03_search_agent/adapters/web_sse/',

  // Folder searched for tests, relative to the repository root.
  testsDir: 'tests',

  // Route decorators such as app.get("/x"), router.post('/x'), api_router.delete("/x").
  // Group 1 is the method, group 2 is the path. A multi line decorator is matched too.
  routeDecorator: /@\w+\.(get|post|put|patch|delete)\(\s*f?["']([^"']+)["']/g,

  // Test function names that suggest each of the three cases.
  validName: /(^|_)(valid|happy|success|ok|accepts?|returns_(200|202|204)|200|202|204)(_|$)/,
  invalidName: /invalid|malformed|bad|reject|422|400|unprocessable|too_long|oversize/,
  emptyName: /missing|empty|none|null|blank|absent|omitted/,

  // Most routes toasted in one turn before the rest are summarised.
  maxToasts: 4,
}
