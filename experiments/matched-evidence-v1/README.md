# Matched evidence and answer-contract experiment

**Nov 18 MYT: better output structure does not establish scoped support.**
The branched schema admitted 7/8 correct supported answers, but also six unsupported
answers and one incorrect literal value. The runtime evidence swap still failed all
four matched question pairs. No production default changed.
[Full report](REPORT.md) · [Layered results](summary.json) · [Frozen protocol](PROTOCOL.md).

## Offline review: no model or network

From the repository root, Python 3.10+ and standard library only:

```bash
python -m unittest discover -s experiments/matched-evidence-v1 -p 'test_*.py' -v
python experiments/matched-evidence-v1/audit_record.py --check
```

`--check` compares parsed Python objects with the committed summary. It avoids shell
redirection encoding and `cmp` requirements and works when called by absolute path
from another directory. It verifies hashes, fixture rebuilding, exact requests,
selector/generator contracts and routing, then recomputes metrics from disclosed
[AI outcome judgments](assistant-review.json). It does **not** independently prove
semantic truth. Labels and outcomes were checked by two AI assistants, not humans.

Frozen audits hash bytes. For a fresh checkout on a system that normally rewrites
line endings, keep this clone's bytes unchanged without changing global Git settings:

```bash
git clone -c core.autocrlf=false https://github.com/zjDing1024/production-rag-system.git
```

The new object-comparison CLI was tested locally on Linux, including invocation
outside the repository. No native Windows test is claimed.

## Optional explicit CPU execution

Linux x86_64/Python 3.12 used here. Allow roughly 586 MB public download and 5 GB RAM
headroom. No paid API, API key or private document is involved.

```bash
python3 experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
python3 experiments/matched-evidence-v1/run_experiment.py \
  --assets /tmp/rag-local-assets --output build/my-matched-evidence-run
```

Choose a new output directory under `build/` each time. The runner verifies frozen
inputs and model/runtime hashes, starts a loopback-only server, stores incremental
results and stops its process. Assets and logs stay outside tracked experiment
records. Memory telemetry is best-effort. Ordinary tests and CI never download or
execute a model.

The same pinned public Qwen3.5-0.8B Q4_0 and official llama.cpp b12359 were used:
[source URLs, revisions, hashes](../local-generation-smoke/sources.json) and
[licenses](../local-generation-smoke/licenses). Model SHA-256:
`57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`;
server SHA-256: `cf07a7d6b6d2c61064105cc0a81360cb5830aacd3d1a949b80eaea3a96fa409f`.
Temperature 0, seed 42, 512 output tokens, thinking off, context 4096, four CPU
threads, one slot, no GPU. The other portfolio timing job ended before this run.

## What is controlled

- Eight exact questions (four families, English/Chinese) each have sufficient and
  insufficient evidence. Documentation and explicitly synthetic runtime scope both
  contain numeric/nonnumeric positive and negative cases. These are new authored
  targets on known source documents, not a held-out corpus or eight independent facts.
- Each row offers two records in the same order and shape, with lengths 227/235
  characters. Source-derived documentation notes and invented snapshots are clearly
  distinguished. Within a pair only relevant documentation fields or the synthetic
  entity name change. No real app, user state or telemetry is read.
- The frozen numbered selector is unchanged. A selected ID resolves to original
  text; that alone does not prove support. Each valid selection triggers both
  generation arms on the exact same selected context. Valid refusals and failures
  skip generation rather than silently excluding cases from the 16-row denominator.
- The generator comparison changes only the wire JSON schema, including a
  4000-character answer bound. Prompt, sampling settings and final Python validator
  stay identical. There is no citation filling, normalization or post-processing fix.
  The interception helper is sequential experimental code, not a thread-safe service.
- [preflight.json](preflight.json) checks old recorded invalid shapes and fresh legal
  fixtures with an original Python shape checker and the existing Python validator.
  This is **not** native GBNF validation. The pinned release has no validator binary;
  no full C++ build was added. Live requests show actual server behavior separately.
- Inputs and protocol were locally frozen in development commit
  `e59a35e32470ebef907af80a55c48ffa6f79a013` before inference. This is local provenance,
  not an externally preregistered or necessarily publicly addressable interim commit.
  [cases.lock.json](cases.lock.json) preserves the content hashes through a squash.

## Artifacts

- [build_fixture.py](build_fixture.py), [cases.json](cases.json): original construction,
  same-question pairs, official-source hash/character anchors and synthetic provenance.
- [protocol.py](protocol.py), [run_experiment.py](run_experiment.py): opt-in mechanism.
- [recorded/manifest.json](recorded/manifest.json), [checksum index](recorded-files.sha256.json):
  16 selector requests, 16 complete result records containing 28 generator requests
  and raw responses, chronological order, fixed hashes and cleanup status.
- [assistant-review.json](assistant-review.json): every row/arm's semantic judgment.
- [summary.json](summary.json): offered coverage, selection, schema/Python contract,
  supported answers, valid refusals, unsupported accepts and whole-pair metrics.

Original code and synthetic data are MIT; source-derived Flask facts retain the
existing BSD-3-Clause attribution. No third-party code, weights or binaries are
included. Earlier experiments remain unchanged as offline regressions.
