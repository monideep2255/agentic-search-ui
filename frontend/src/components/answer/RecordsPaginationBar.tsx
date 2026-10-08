/**
 * The "Showing 1–10 of 20" bar with Previous and Next, shared by the live
 * answer (`AnswerScreen.tsx`) and a reopened saved answer
 * (`savedAnswerMarkdown.tsx`) so the two cannot drift apart (card 71).
 * Moved out of `AnswerScreen.tsx` unchanged: same markup, same test ids.
 */

import { Box } from "@mui/material";

import { designTokens } from "../../theme";

export const RECORDS_PAGE_SIZE = 10;

export function RecordsPaginationBar({
  testIdBase,
  currentPage,
  totalPages,
  totalRows,
  onGo,
}: {
  /** Test id stem, e.g. `answer-records-0`; the bar adds `-pagination`, `-status`, `-prev`, `-next`. */
  testIdBase: string;
  currentPage: number;
  totalPages: number;
  totalRows: number;
  onGo: (page: number) => void;
}) {
  const start = currentPage * RECORDS_PAGE_SIZE + 1;
  const end = Math.min(start + RECORDS_PAGE_SIZE - 1, totalRows);
  const navSx = {
    font: "inherit",
    fontSize: 13,
    fontWeight: 600,
    border: 0,
    bgcolor: "transparent",
    color: designTokens.link,
    cursor: "pointer",
    p: 0,
    "&:disabled": { color: designTokens.inkFaint, cursor: "default" },
  } as const;
  return (
    <Box
      data-testid={`${testIdBase}-pagination`}
      sx={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "8px 16px",
        fontSize: 13,
        color: designTokens.inkMuted,
        m: "0 0 16px",
        pt: "8px",
        borderTop: `1px solid ${designTokens.line}`,
      }}
    >
      <Box component="span" aria-live="polite" data-testid={`${testIdBase}-status`}>
        {`Showing ${start}–${end} of ${totalRows}`}
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <Box
          component="button"
          type="button"
          data-testid={`${testIdBase}-prev`}
          onClick={() => onGo(currentPage - 1)}
          disabled={currentPage === 0}
          sx={navSx}
        >
          {"‹ Previous"}
        </Box>
        <Box component="span" sx={{ color: designTokens.inkFaint, fontSize: 12.5 }}>
          {`Page ${currentPage + 1} of ${totalPages}`}
        </Box>
        <Box
          component="button"
          type="button"
          data-testid={`${testIdBase}-next`}
          onClick={() => onGo(currentPage + 1)}
          disabled={currentPage >= totalPages - 1}
          sx={navSx}
        >
          {"Next ›"}
        </Box>
      </Box>
    </Box>
  );
}
