# Explicit English input correction after initial recording

The original recorded English hidden sentences unexpectedly overlap their question
on token `is`. The first full input-invariant test found this after the original
22-case run; original cases, protocol, freeze and raw results remain unchanged.
Those original English controls establish lower-rank omission at k=1, not zero
lexical visibility. Chinese and path controls already have genuinely zero overlap.

This separate two-case supplement changes only the English hidden sentence from
`The configured duration is ...` to `Configured duration: ...`, updating its source
hash/span binding and index fingerprint. Both original scopes, reviewed values,
question, IDs, options and expected routes are preserved. Before execution, assert
empty token intersection and matched agreement/conflict text lengths, then freeze
these new inputs. Reuse the original unmodified pipeline and runner through its
existing directory argument. No output tuning, model calls or threshold changes.

Expected agreement calls the spy; conflict stops before ranking/calling. Both
baseline k=1 views still contain only h7. Do not count these two related repaired
rows as independent new facts or suppress the original input failure.
