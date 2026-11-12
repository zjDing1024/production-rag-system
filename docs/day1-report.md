# Day 1 report · 2026-11-12

## Delivered scope

- Original standard-library ingestion, deterministic source-span chunking,
  inverted-index BM25, CLI, evaluation, and tests.
- Six unmodified Flask 3.1.0 documentation files, 99,096 bytes, under BSD-3-Clause.
- 91 overlapping source chunks with fixed upstream commit and source line links.
- 22 authored development questions: 18 answerable and four unanswerable.
- No embedding model, language model, generated answer, external API, or deployment.

The learning value is provenance, transparent scoring, testable retrieval, and
honest negative-case measurement. Completion of this assisted artifact is not
evidence of the learner's independent mastery.

## Protocol fixed before the first retrieval run

Corpus commit: `ab8149664182b662453a563161aa89013c806dc9`.
Question-file SHA-256:
`30b677b040466b3636cfd3182ef110924444d70e0a1a6feb368079b3809d28ca`.

The questions and their source quotations were authored and validated against
the corpus before the first index/query evaluation. No parameter sweep was run.
The first retrieval result was retained without revising queries or parameters
to improve the score. The set was built by someone who could see the corpus,
so it remains a development set, not held-out evidence.

Fixed configuration: 180 whitespace words per chunk, 40-word overlap,
Unicode `\w+` casefold tokenization, no stop-word filter, no stemming,
distinct query terms, BM25 k1=1.5 and b=0.75, top five chunks.
Relevance requires the complete whitespace-normalized gold quotation in its
specified document. Incomplete judgments may exclude other useful passages.

## Actual results

| Metric | Result |
|---|---:|
| Hit@1 | 12 / 18 = 0.6666667 |
| Hit@3 | 16 / 18 = 0.8888889 |
| Hit@5 | 17 / 18 = 0.9444444 |
| MRR@5 | 0.7916667 |
| Unanswerable queries returning at least one chunk | 3 / 4 = 0.75 |

Raw scored IDs, evidence matches, line citations, and hashes are retained in
[`results/day1-evaluation.json`](../results/day1-evaluation.json).

### Observed failures and cautions

- q01, accepting POST on a route: target evidence first appears at rank 4.
- q05, q10, q14, q16: target evidence first appears at rank 2, not rank 1.
- q18, a Chinese query about a test client's need for a live server: no gold
  evidence in the top five. Unicode token recognition is not multilingual retrieval.
- q19, Kubernetes GPU configuration; q20, the latest release today; and q22,
  Malaysian hosting prices: all return five chunks, although the pinned corpus
  cannot answer those questions. This baseline has no answerability filter.
- q21 is an artificial no-overlap sentinel and correctly returns no results.
  It must not be used to imply effective real-world refusal behavior.

No generation occurs. Answer accuracy, groundedness, hallucination rate, and
end-user task success were not measured.

## Verification executed locally

Python 3.12.14, Linux x86_64:

1. `PYTHONPATH=src python -m unittest discover -s tests -v`: **34 tests passed**.
2. `python -m compileall -q src tests examples`: passed.
3. `python -m rag_foundation ingest`: verified six source documents, emitted 91 chunks.
4. `python -m rag_foundation evaluate`: wrote the retained report.
5. `python -m rag_foundation query 'test client live server' -k 3`: wrote the example.
6. Built a wheel with no runtime dependencies, installed it in a fresh virtual
   environment, then ran all **34 tests against the installed package** with
   `PYTHONPATH` removed. Passed.
7. Re-evaluated using the installed wheel and compared the complete report bytes
   with `results/day1-evaluation.json`. Identical.

Checks include corpus/license tampering, fixed upstream Git blob hashes, missing
files, parent/absolute/symlink path escapes, chunk bounds/overlap/coverage,
stable identifiers, hand-computed BM25, parameter validation, ties, no matches,
known evaluation metrics, stale gold evidence, CLI failure, and end-to-end output.

Source and wheel runs exercise the same 34 tests, not 68 distinct checks.
The workflow additionally defines Python 3.11/3.12 remote checks; a workflow file
alone is not evidence of a successful remote run. Consult the exact commit's
Actions status for publication validation.

## Small-corpus timing observation

[`results/day1-latency.json`](../results/day1-latency.json) records one local run:

- Verified load + chunk + index, one run: **29.65 ms**.
- 22 warm-up queries, then 10 passes of all 22 questions: **220 timed searches**.
- Warm query median: **0.199 ms**; nearest-rank p95: **0.304 ms**.

These query times exclude corpus ingestion, process startup, disk output, and
any model calls. No concurrency, production hardware, persistent service,
memory profile, or corpus scale experiment was tested. Timings vary by machine
and scheduling, so they are stored separately from the deterministic report.

Re-run:

```bash
PYTHONPATH=src python examples/benchmark_retrieval.py --output build/latency.json
```

## Next useful experiment

First add independently reviewed English paraphrases, Chinese queries, and
realistic missing-answer cases without tuning on the same evaluation set.
Compare lexical, dense, and hybrid retrieval under a frozen relevance protocol.
Only after retrieval is measured should a generator and citation/abstention
checks be added. Paragraph-aware boundaries and duplicate-window diversity are
also concrete next improvements, rather than premature production claims.
