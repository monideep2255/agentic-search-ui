# Draft note to NCBI about a MedGen encoding error

For the product owner to send through NCBI's support form (https://support.nlm.nih.gov/) if they choose. Nothing has been sent.

## The note

Subject: MedGen record C1321489 name shows broken character encoding

Hello,

The MedGen record for Muir-Torré syndrome (concept C1321489, MedGen UID 231157) returns its name with a broken character: "Muir-TorrÃ© syndrome" instead of "Muir-Torré syndrome".

How to see it:

- E-utilities: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=medgen&id=231157&retmode=json`
- The response is labelled UTF-8, and the name field carries the bytes `54 6f 72 72 c3 83 c2 a9` ("Torr" followed by "Ã©"), where "é" would be `c3 a9`. The XML form carries the same bytes.

This looks like UTF-8 text that was decoded as Latin-1 and encoded again somewhere upstream of the summary. Other records may carry the same pattern.

Thank you.

## Evidence

The byte trace is `testing/Developer/reports/2026-10-05_card96/source_trace.md`. The product repairs this pattern on arrival since #170, so the note is a courtesy to NCBI, not a dependency.
