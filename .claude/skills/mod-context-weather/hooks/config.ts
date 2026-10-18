// Per-repository settings for mod-context-weather.
export const config = {
  // Minutes the prompt cache stays warm after a turn.
  cacheTtlMinutes: 5,
  // Minutes of idle time after a turn before the nudge may fire.
  idleNudgeMinutes: 4,
  // The nudge only fires above this many context tokens.
  nudgeAboveTokens: 60000,
}
