# Encoding Investigation: MedGen:C1321489

Date: 2026-10-05  
Investigation: Is "Muir-Torré syndrome" (MedGen C1321489) stored garbled in the knowledge graph?

## Query Method

Used the app's own graph connection mechanism via `<repo-root>/src/system_03_search_agent/tools/graph_connection.execute_cypher()`, querying the AGE graph running on Hetzner VPS via HTTPS transport (`GRAPH_QUERY_URL`).

## Query Executed

```cypher
MATCH (a:Disease {id: $disease_id})
RETURN a
```

Parameters: `{"disease_id": "MedGen:C1321489"}`

## Results

The identifier MedGen:C1321489 was found in the graph. Its properties are:

```json
{
  "id": "MedGen:C1321489",
  "label": "Disease",
  "name": "MONDO",
  "source": "MedGen",
  "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C1321489",
  "xrefs": "",
  "agent_type": "",
  "knowledge_level": ""
}
```

## Encoding Analysis

The name value is: `'MONDO'`

UTF-8 bytes (hex): `4d 4f 4e 44 4f`

Character breakdown:
- `M` → `4d`
- `O` → `4f`
- `N` → `4e`
- `D` → `44`
- `O` → `4f`

### Finding

**The data is stored CORRECTLY in the graph with proper UTF-8 encoding.** The name "MONDO" contains only ASCII characters (bytes 0x20-0x7E), so no encoding issues exist.

**However:** The identifier MedGen:C1321489 does NOT correspond to "Muir-Torré syndrome" at all—it corresponds to "MONDO" (an ontology name). No disease named "Muir-Torré syndrome" or any variant of it was found in the knowledge graph using substring searches for "Muir", "Torre", or "Torré".

Additionally, a scan for diseases containing the garbled-encoding marker character "Ã" (UTF-8 bytes `c3 83`, which indicates double-encoding) found no such diseases in the graph.

## Conclusion

**The question cannot be answered as posed because:** The identifier MedGen:C1321489 does not belong to "Muir-Torré syndrome" in the knowledge graph. The value stored at this identifier ("MONDO") is correctly encoded UTF-8, with no corruption. If the app displays "Muir-TorrÃ© syndrome" anywhere, it is either:

1. A different identifier than C1321489, or
2. A decoding error in the application layer (the way the app reads or displays graph data), not in the graph storage itself.

To proceed, confirm the correct MedGen identifier for "Muir-Torré syndrome" and re-run this check.
