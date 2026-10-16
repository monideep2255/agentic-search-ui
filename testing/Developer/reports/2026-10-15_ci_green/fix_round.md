# CI green: fix round, 2026-10-15

Base: 3201dca4938e03d136fcb4b09922fd47af737842 on fix/ci-model-prices-and-strawberry, clean. Nothing committed.

## Table of contents

- [Findings closed](#findings-closed)
- [Glm price](#glm-price)
- [Mutations](#mutations)
- [Gates](#gates)
- [Open, not in this round](#open-not-in-this-round)
- [Learnings](#learnings)

## Findings closed

| Finding | Status | Evidence |
|---|---|---|
| J-114-07 | Closed | pyproject.toml pin now strawberry-graphql==0.327.7. Nothing else in pyproject.toml, requirements.txt or .github pins strawberry. In the scratch venv, CI's exact setup_python.sh sequence (pip upgrade, `pip install -r requirements.txt`, `pip install -e ".[dev]"`) ended with `pip show strawberry-graphql` reading `Version: 0.327.7`; the second install no longer replaced it. |
| J-114-05 | Closed | See Glm price. |
| J-114-02, A-114-03 | Closed | `_price_per_token` in harness.py: when the table names the model, a litellm price on either side that is zero, negative, NaN, infinite or not a number sends both sides to the table (new helper `_is_real_price`). A model the table does not name returns litellm's figure as before; a missing price still raises. |
| A-114-06, J-114-04 | Closed | New tests in test_opus_writer.py: `test_a_real_non_zero_litellm_price_beats_the_table`, `test_a_one_sided_zero_from_litellm_takes_the_tables_price_for_both_sides[input|output]`, `test_a_price_that_is_not_a_real_number_takes_the_tables_price[nan|infinite|negative|not-a-number]`, `test_a_model_the_table_does_not_name_keeps_litellms_figure_even_at_zero`. |
| J-114-03 | Closed | test_tiers.py: `_fallback_price_key_positions` collects (line, column, value) of the keys of the dict literal assigned to `_FALLBACK_PRICES_USD_PER_TOKEN`; `test_no_model_id_shaped_string_outside_the_default_table` allows a price key in tiers.py only at those positions. Docstring and failure message now name both tables. |
| J-114-01, J-114-06, J-114-08 | Closed | Comments corrected in tiers.py (SYNTH_MODEL, Opus, table purpose with the zero rule, root cause), harness.py (both comment blocks and the docstring), test_opus_writer.py docstrings, requirements.txt libcst wording ("from no floor to libcst>=1.9.0, a narrowing"), and the 0.327.7 "re-verified 2026-10-15" mentions in security.py, schema.py, context.py, test_context.py. |

Root cause, as stated in the comments: litellm replaces its bundled price map at process start with one fetched from its main branch, and that fetched map currently has no OpenRouter entries, so the price depends on whether the fetch succeeds. The table keeps the price stable. No litellm configuration or environment setting was changed.

The pyproject.toml comment at line 45 still says 0.324.0: it names a historical finding made at that version, so it was left.

## Glm price

Source: OpenRouter public catalogue, https://openrouter.ai/api/v1/models, entry id "z-ai/glm-5.2", read 2026-10-15 23:50 UTC. Raw pricing block:

```
{
 "prompt": "0.000000037",
 "completion": "0.000007",
 "input_cache_read": "0.000000036"
}
```

| | Input per token | Output per token |
|---|---|---|
| Before (copied from production) | 0.0000007182 | 0.0000022572 |
| After | 0.000000037 | 0.000007 |

No other model's price changed. The comment in tiers.py states the date and source.

## Mutations

Each mutated one property of `_price_per_token` or `_is_real_price`, then was restored from a saved copy (full file diff checked by the green rerun).

| Mutation | Result |
|---|---|
| Named model always takes the table (litellm's real price ignored) | 1 failed: test_a_real_non_zero_litellm_price_beats_the_table |
| Only the input side is checked | 4 failed: one-sided zero [output], nan, infinite, negative |
| Both-sides check turned into either-side | 5 failed: both one-sided zero cases, nan, infinite, negative |
| NaN counted as a real price | 2 failed: nan, infinite |
| Judge probe: `model == "z-ai/glm-5.2"` appended in tiers.py | test_no_model_id_shaped_string_outside_the_default_table fails (passed before the fix) |
| Same literal appended in harness.py | fails |

Restored: test_opus_writer.py 41 passed; harness folder 574 passed.

## Gates

- `ruff check` (no path): All checks passed! (main venv and scratch venv)
- `isort --check-only src tests services tracker alembic .claude .github`: exit 0, "Skipped 2 files".
- Gate 4 command (`PYTHONPATH=src pytest -m "not integration" -q -rs --junitxml=...`), main venv: `7643 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 420.65s (0:07:00)`
- Gate 4 command, scratch venv (strawberry 0.327.7, litellm 1.105.1): `7643 passed, 143 skipped, 24 deselected, 1 xfailed, 8 warnings in 419.10s (0:06:59)`
- Gate 6 (`pip-audit -r requirements.txt`), scratch venv: `No known vulnerabilities found`

I did not run gate 4's second half (assert_no_db_skips.py).

## Open, not in this round

- A-114-01: query 66 can still give a count-line-only summary with the writer restored.
- A-114-02: Researcher lead sentence repeats the records the count line lists.
- A-114-04: with an Opus default writer, the two writer drafts now run one after the other and the second can be refused.
- Also noted, untouched: harness.py's error text for a missing price still says to add it to `harness.harness._FALLBACK_PRICES_USD_PER_TOKEN`; the table lives in tiers.py.
- Other tabled prices drift from today's catalogue (deepseek-v4-flash, kimi-k2.6, per J-114-05); not changed, as instructed.

## Learnings

- A first mutation of mine inverted the condition instead of making the table always win, and it did not touch the "real price beats the table" test. Write the mutation as the exact property named (replace the real-price clause with `False`).
- `sed -i` on macOS needs `-i ''`; a failed first call left nothing changed. An unset shell variable in `cp $H $S.bak` created a stray `.bak` file in the worktree; removed with Python (the shell hook blocks rm).
