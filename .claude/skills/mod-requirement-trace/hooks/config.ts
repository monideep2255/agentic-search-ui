// Per-repository settings for mod-requirement-trace. Paths are relative to the repository root.
export const config = {
  /**
   * Cards live in a table whose first column is the card number and whose second column is its title.
   * The board froze at build phase 6.2 on 2026-09-25 and the cards moved here.
   */
  cardsFile: 'testing/UI_fix_plan.md',
  /** The frozen build board: a table whose first column is the phase step and whose third column is what it delivers. */
  boardFile: 'tracker/BOARD.md',
  /** Meeting notes. Only their file names and heading lines are ever read out. */
  meetingsDir: 'requirements/meetings',
  /** Characters of title shown in the status line. */
  titleChars: 50,
  /** Heading lines listed per file by /trace. */
  maxHeadingsPerFile: 8,
  /** A bare number such as "3.5 seconds" is a measurement, not a phase, when one of these follows it. */
  unitWords: ['s', 'sec', 'secs', 'second', 'seconds', 'ms', 'min', 'mins', 'minute', 'minutes', 'hour', 'hours', 'x', 'k', 'mb', 'gb', 'kb', 'percent', 'dollars', 'cents'],
}
