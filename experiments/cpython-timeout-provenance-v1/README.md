# CPython timeout provenance: separate duration, evidence scope and locator

From the repository root using standard-library Python 3.10+:

```bash
python -B experiments/cpython-timeout-provenance-v1/audit.py --case py311-connection-shutdown
python -B experiments/cpython-timeout-provenance-v1/audit.py --case py311-connection-shutdown-removed
python -B experiments/cpython-timeout-provenance-v1/audit.py --check
python -B experiments/cpython-timeout-provenance-v1/live.py --check
```

The first two commands use the identical question with and without its reviewed
evidence. The visible output is a deterministic plan, not generated text. It
exposes an audited typed integer/unit and an exact citation ID/URL from the
reviewed plan when eligible. The other commands audit the checked-in reports
without a model, downloads, or network. The general new module is
`PYTHONPATH=src python -B -m rag_foundation.provenance_pipeline --help`; it
accepts the operator-owned chunks/catalog and query/scope request JSON from
[the indexed pipeline](../../docs/indexed-scope-pipeline.md).

## Mechanism and measured offline results

The opt-in renderer leaves a nonempty upstream fragment untouched and stores
`local_span` separately (start/end character offsets and inclusive line span).
For whole-source chunks without a source fragment, it renders the stored
chunk-local line range as one fragment. This only forms an accurate upstream
line link if the operator's coordinates align with the supplied whole source.
Ranked hits, packed context, and final model citation IDs use the same
`provenance` entries; final citations only resolve IDs actually packed. No URL
is followed, authenticated, or rewritten by the model. Provenance is not
semantic entailment. Historic paths and locked receipts, including their old
display format, are unchanged.

Three planned scopes use the exact typed values and source locators:
* CPython 3.11.0 client TLS **shutdown**: 30 seconds, [L475–477](https://github.com/python/cpython/blob/deaf509e8fc6e0363bd6f26d52ad42f976ec42f2/Doc/library/asyncio-eventloop.rst#L475-L477).
* Same release, **server** TLS shutdown: 30 seconds, [L708–710](https://github.com/python/cpython/blob/deaf509e8fc6e0363bd6f26d52ad42f976ec42f2/Doc/library/asyncio-eventloop.rst#L708-L710).
* Same release, client TLS **handshake**: 60 seconds, [L471–473](https://github.com/python/cpython/blob/deaf509e8fc6e0363bd6f26d52ad42f976ec42f2/Doc/library/asyncio-eventloop.rst#L471-L473).

Two cases stop before ranking with `no_matching_scope`: remove the client
shutdown evidence from the same 3.11 pool, or pin the older release where
the [3.10.0 client signature](https://github.com/python/cpython/blob/b494f5935c92951e75597bfe1c8b1f3112fec270/Doc/library/asyncio-eventloop.rst#L367-L372)
does not expose the option. Absence is not a zero or null duration.
In a separate real unscoped top-1 probe, the supported 3.11 client-shutdown
question selected handshake. When the client evidence was removed the same
probe selected the server shutdown record with the same 30; the old-release
probe found older handshake. These are retrieval diagnostics, not unscoped
model results. See [offline report](report.json) and [frozen inputs](oracle.json).

All record summaries are original MIT-licensed fixture text, not copies of
[CPython upstream PSF-2.0 material](https://github.com/python/cpython/blob/deaf509e8fc6e0363bd6f26d52ad42f976ec42f2/LICENSE).
[Source manifest](source-manifest.json) pins both releases, checked byte hashes,
and exact source intervals. No TLS runtime behavior was tested.

## Three actual local CPU requests

The [protocol](PROTOCOL.md), typed scorer, controls, and
[lock](live.lock.json) were frozen before the optional run
(lock SHA-256 `ca02dc42dc815399f5539367b8f06b1aad98fed04fffbcfc8a9249a188a7fee9`).
Qwen3.5-0.8B Q4_0 (Apache-2.0 base) and llama.cpp b12359 (MIT) were free, pinned,
checksum-verified [assets](../local-generation-smoke/sources.json).
The [receipt](recorded-live.json) preserves full payloads, raw responses,
and exact scoring; offline audit replays the adapter, not inference.

| Scoped-only outcome | Recorded |
| --- | --- |
| Answer branch, correct reviewed chunk ID and exact source URL | 3/3 admitted |
| Integer value plus required unit plus exact reviewed origin | 0/3 admitted |
| Deterministic no-call before ranking | 2/2 insufficient |
| Model abstention / invalid response / transport error | 0 / 0 / 0 |

The returned strings were `"30"`, `"30"`, and `"60"`. All three integers
match the reviewed numbers in a separate literal diagnostic, but all omit
`seconds`. We did not relax the rubric, infer a unit, or count them as complete
answers. The three authored [scorer controls](scorer-controls.json) are not
additional inference: wrong method, negation and example-only mentions all
include the gold-looking number and unit while failing claim review.
No unscoped CPU arm, independent held-out test, or latency measurement.

For an explicit standalone repeat on Linux x86_64 (public download ~586 MB;
normal tests and CI do not download these files or run a model):

```bash
python -B experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
mkdir -p build
python -B experiments/cpython-timeout-provenance-v1/live.py --assets /tmp/rag-local-assets > build/cpython-timeout-live.json
```
