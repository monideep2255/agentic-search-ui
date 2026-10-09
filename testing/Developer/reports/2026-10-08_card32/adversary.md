# Card 32 adversary, round 1

- Checkout: card32-adv, HEAD ee09aff5a10c56618cb5ebebb7426c09fc2c5572, merge base with origin/develop c916cfa30f59802dfd85c81ef7ba39bdcfc2b263
- Method: own probes (small scripts and single test files), no live model calls

## Findings

### A-32-01: INSIDE THIS CARD'S FIX: the rename can collide with a second column's real alias and silently drop a value
- Severity: major (the trigger needs the model to write both aliases, so it is rare; the failure is silent data loss, the exact shape `column_labels_for` already guards against for duplicate aliases)
- What: `_graph_field_name` maps `clinical_features` to `graph_clinical_features` without checking whether that name is already taken. A RETURN carrying both aliases collapses two columns onto one key in the dict comprehension in `_shape_derived_value`; the first column's value disappears with no note. `column_labels_for` explicitly keeps both columns positional on a duplicate alias ("A duplicate alias would collapse two columns onto one key and silently drop a value"), and the rename reintroduces that loss after its check.
- Reproduction: p32a.py at HEAD ee09aff5. `column_labels_for("MATCH (g:Gene) RETURN count(g) AS clinical_features, 7 AS graph_clinical_features")` gave `{'c0': 'clinical_features', 'c1': 'graph_clinical_features'}`; `to_output_rows({"c0": "3", "c1": "7"}, ..., column_labels=labels)` gave `[{'graph_clinical_features': 7}]`. The 3 is gone. Same for `hpo_id`/`graph_hpo_id`, `disease_title`/`graph_disease_title`, `clinical_features_total`/`graph_clinical_features_total` by construction.
- What a person sees: an answer built from one of two numbers the graph returned, with no sign the other existed. On origin/develop the same query kept both values (as `clinical_features` and `graph_clinical_features`).
- NOT FIXED
### A-32-02: a graph vertex whose properties carry a reserved name is not renamed; only derived values are guarded
- Severity: minor (unsure: System 1 and 2's MedGen parsers in `reference/` do not write these property names today, so no live graph row is known to trigger it)
- What: the guard sits only in `_shape_derived_value`. `_shape_entity` copies `fields = dict(properties)` unchanged, so a vertex or edge property named `clinical_features`, `hpo_id`, `disease_title` or `clinical_features_total` still reaches every consumer that keys on the name alone (graph.py lines 8871, 12042, 12362 to 12403; findings.py 1235 to 1268, 1808, 1875).
- Reproduction: p32a.py. A `Disease` vertex with properties `{"id": "MedGen:C0024796", "name": "Marfan", "clinical_features": "Tall stature", "hpo_id": "HP:0000098"}` shaped to `entity: [{'id': 'MedGen:C0024796', 'name': 'Marfan', 'clinical_features': 'Tall stature', 'hpo_id': 'HP:0000098'}]`.
- What a person sees: should the graph ever carry such a property (a future System 2 load, or an edge property), a graph value is presented as MedGen's clinical feature list, the defect the ticket names. The card's comment says the rename is applied "where a Layer 1 field name is born", but one birthplace is not covered.
- NOT FIXED
### A-32-03: the renamed field still reads as "clinical features" to the writing model, cited to the MedGen page
- Severity: unsure (model behaviour, not probed: no live model calls this round)
- What: the rename keeps the reserved word inside the new name (`graph_clinical_features`, `graph_hpo_id`, `graph_disease_title`). Code-side consumers compare by equality and are now protected. The field name and value still reach the Synth prompt, and a derived row on a MedGen Disease CURIE cites the MedGen record page, so the model can still write "MedGen lists these clinical features [n]" over a graph value.
- Reproduction: structural. `to_output_rows({"c0": "3"}, ..., derived_source_curie="NCBIGene:2200", column_labels={"c0": "clinical_features"})` gives `{"graph_clinical_features": 3}` (the card's own test asserts exactly this name). Findings carry the field name verbatim (`findings.py` line 664, `field=_clip(field_name, ...)`).
- What a person sees: possibly the same mislabel in prose, without the clinical-features panel. The card closes the code path only.
- NOT FIXED
## Verdict

- FAIL. A-32-01 sits INSIDE THIS CARD'S FIX: the rename silently drops a column's value when the renamed key is already a real alias, the duplicate-key loss `column_labels_for` exists to prevent. Escalation condition for the review loop.
- Verified by my own probes: A-32-01 (collision), A-32-02 (vertex properties pass unrenamed), alias variants (backtick alias gives no label, `Clinical_Features` is not renamed and matches no consumer, trailing space is stripped). Read only: consumers key by exact equality (graph.py, findings.py), no template in `cypher_templates.py` aliases a reserved name, the MedGen feature rows are built in graph.py and do not pass through this code, A-32-03.
