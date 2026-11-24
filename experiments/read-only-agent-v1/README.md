# Read-only document agent: bounded local evidence workflow

An opt-in, deterministic agent-style workflow over six bundled summaries. It
resolves a reviewed request ID to an exact documented scope, checks the matching
catalog, retrieves locally, and cites one reviewed value or stops. No model,
downloads, external tools, arbitrary file paths, shell commands, SQL, outbound
networking, or data writes are part of this product path. Source links are printed
as metadata, not opened. Existing RAG/LLM paths and defaults are unchanged. The
acceptance harness uses a child process solely to exercise the real CLI; it is not
callable by the agent.

## Run and inspect

From the repository root, Python 3.10+, standard library only:

    PYTHONPATH=src python -B -m rag_foundation.safe_document_agent --list
    PYTHONPATH=src python -B -m rag_foundation.safe_document_agent express-5-default
    PYTHONPATH=src python -B -m rag_foundation.safe_document_agent cpython-color-retry
    PYTHONPATH=src python -B -m rag_foundation.safe_document_agent cpython-color-retry --max-retrievals 1
    PYTHONPATH=src python -B -m rag_foundation.safe_document_agent express-5-default --expect-scope-of express-4-default

The Express CLI returns the string simple with its original summary and pinned
source. The CPython example intentionally starts with zero lexical matches. It
retries once using a pre-reviewed alias without changing scope. A one-attempt
budget stops instead. A crossed expected scope stops before retrieval. Results
go to stdout; Python -B avoids writing interpreter caches.

## What is bounded

- Only a fixed intent registry binds requests; an optional expected scope must
  match subject, version and predicate exactly. Unknown intent or mismatch stops
  before retrieval, not after a potentially wrong citation.
- Existing ClaimIndex completeness/conflict checks run before ranking. Missing
  evidence, an unreviewed claim, a conflict or packing failure is not retried.
  Only zero lexical candidates can use the one reviewed fallback. There is no
  free-text tool choice, interpreted command, or generated search query.
- The entire bundled corpus is capped at 16 chunks and 4,096 text characters
  (six actual chunks). At most two retrieval attempts, two top-1 ranking passes,
  128 characters per configured query, and 512 context characters are allowed.
  These caps don't measure inner indexing operations or latency.
- Rendering uses a reviewed typed catalog value, not model text. It validates
  ID, exact scope, citation locator, summary and span before citing. The SHA is
  for the original summary, **not** the upstream source file. This does not
  test semantic entailment.
- Output includes bound scope, attempted strategies, preflight decisions, lexical
  hit counts, packed IDs and final cite or stop. A preflight-only attempt is
  not a BM25 ranking; neither involves calling a model.

## Observed acceptance run

| Cases | Result |
|---|---|
| Two Express versions and the CPython alias retry | 3 reviewed, cited values |
| Retrieval cap, packing cap, conflict, missing, unreviewed, wrong binding, unknown intent | 7 explicit stops |
| Retrieval attempts / actual ranking passes | 9 / 6 |
| Maximum retrieval attempts in any case / model requests | 2 / 0 |

One same-scope conflicting record has no lexical overlap. The preflight still
stops before scoring either. Separate unit tests show that a live catalog ID
with the wrong scope or changed locator cannot be cited. These are designed
acceptance rows, not a population accuracy estimate.

    python -B experiments/read-only-agent-v1/replay.py --check
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -p test_safe_document_agent.py -v

The replay executes the actual CLI ten times, checks independent expected
outcomes, and compares its result with [report.json](report.json) byte-for-byte.
CI uses no model or network services for the tests.

## Sources and limitations

- [Express 4.21.2 default][express4], [Express 5.1.0 default][express5]
  ([MIT][express-license]), and [CPython 3.14.0 argparse defaults][cpython]
  ([PSF License v2][python-license]). Original summaries are MIT project fixtures, not upstream text. CPython's
  Boolean is a canonical string in the existing catalog type. DemoBox is synthetic.
- Design comparison: [OpenAI Agents SDK turn budget][sdk-budget] tracks model
  turns. This workflow has no model loop and counts retrieval and rankings
  separately. [Tool enablement][sdk-tools] and [authorization notes][sdk-auth]
  inform the boundary, not the implementation ([MIT][sdk-license]).
- This is not general natural-language Q&A, semantic support verification,
  user authorization, or an autonomous tool-calling system. The trusted operator
  supplies the intent map and reviewed facts. No upstream code was copied.

[express4]: https://github.com/expressjs/express/blob/1faf228935aa0a13111f92c28ee795be64ce3f0f/lib/application.js#L80-L86
[express5]: https://github.com/expressjs/express/blob/cd7d4397c398a3f3ecadeaf9ef6ac1377bd414c4/lib/application.js#L93-L100
[express-license]: https://github.com/expressjs/express/blob/cd7d4397c398a3f3ecadeaf9ef6ac1377bd414c4/LICENSE
[cpython]: https://github.com/python/cpython/blob/ebf955df7a89ed0c7968f79faec1de49f61ed7cb/Lib/argparse.py#L1877-L1881
[python-license]: https://github.com/python/cpython/blob/ebf955df7a89ed0c7968f79faec1de49f61ed7cb/LICENSE
[sdk-budget]: https://github.com/openai/openai-agents-python/blob/4e162c79a4a951c6fc8b698d5c8279c1963c099b/src/agents/run.py#L309-L324
[sdk-tools]: https://github.com/openai/openai-agents-python/blob/4e162c79a4a951c6fc8b698d5c8279c1963c099b/src/agents/agent.py#L290-L319
[sdk-auth]: https://github.com/openai/openai-agents-python/blob/4e162c79a4a951c6fc8b698d5c8279c1963c099b/docs/tools.md#L902-L915
[sdk-license]: https://github.com/openai/openai-agents-python/blob/4e162c79a4a951c6fc8b698d5c8279c1963c099b/LICENSE
