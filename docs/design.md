# Design and source study

## Corpus contract

The offline source of truth is `data/manifest.json`. It binds six exact Flask
3.1.0 document blobs to a reviewed BSD-3-Clause license and a fixed upstream
commit. The importer verifies checksums and size before decoding UTF-8. The
manifest is a reviewed repository input, not a signature or proof of trusted
authorship: someone able to alter both data and manifest can change the corpus.

Source URLs are provenance, not fetched at runtime. Only a local manifest-listed
file is loaded; parent-path and symlink escapes from the chosen root are rejected.
JSONL chunks are local derived artifacts. `read_chunks` validates their basic
shape and spans, but does not authenticate them against the original sources.
Regenerate from the reviewed manifest for trusted evaluation; do not ingest
untrusted chunk files as authoritative evidence.

## Chunking trade-off

The first baseline uses 180 whitespace words per window with 40 words of overlap.
This is **not** an LLM token limit. The last window ends with the last source word;
no redundant all-overlap tail is emitted. Each chunk contains an exact source
substring, half-open character offsets, and inclusive 1-based line numbers.
Chunk identity binds document ID, complete source SHA-256, and character span.

Raw RST directives, code examples, and headings stay in the searchable text.
This makes provenance simple but can split a code block or pollute term counts.
Overlap helps short evidence spans fit inside a chunk and also creates correlated
near-duplicate candidates. We do not claim semantic or structure-aware chunking.
Chunk length and overlap were fixed before the first evaluation, with no sweep.

## BM25 from the scoring equation

`N` is the number of chunks, `df` the number of chunks containing a term, `tf`
its frequency in a chunk, and `L` the chunk's token count. Here “document
frequency” therefore means **chunk** frequency, not original-file frequency.

```text
idf(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
score(q,d) = Σ idf(t) * tf(t,d) * (k1 + 1)
             / (tf(t,d) + k1 * (1 - b + b * L(d)/avgL))
```

The sum uses sorted distinct query tokens. Duplicate query words do not amplify
scores. `k1=1.5` controls saturation; `b=0.75` normalizes by length. A hand-computed
two-chunk fixture verifies the numeric score. Empty/no-overlap queries return an
empty list. We do not remove stop words, stem, split underscores, translate,
boost titles, or normalize scores into probabilities. `\w+` with casefold is a
small Unicode lexical policy, not effective Chinese segmentation.

## Source study: Apache Lucene BM25Similarity

Reference inspected:
[Lucene 9.12.0 BM25Similarity, lines 25–120](https://github.com/apache/lucene/blob/releases/lucene/9.12.0/lucene/core/src/java/org/apache/lucene/search/similarities/BM25Similarity.java#L25-L120).
Repository: [apache/lucene](https://github.com/apache/lucene), maintained by the
Apache Lucene project. Lucene is a mature search engine; its similarity layer
isolates scoring from index representation and token analysis.

The inspected constructor validates finite saturation parameters and bounded
length normalization. Its IDF function uses the same positive log form, while
its default `k1=1.2` differs from this deliberately fixed `1.5` baseline. It also
accounts for token overlap positions and compact length encoding, which this
project does not implement. We reuse the mathematical idea and separate scoring
from ingestion, not Lucene source code. No parity claim with Lucene is made.

Useful engineering lesson: a score depends on tokenizer, field statistics,
length policy, and query semantics, not just a function named “BM25.” The entire
small baseline is specified and tested before adding embedding dependencies.

## Evaluation contract

The 22-question development file was written against the pinned source before
the first retrieval run. A gold hit requires the right document ID and the full
whitespace-normalized evidence quotation inside a returned chunk. Questions may
have more than one gold evidence item; any qualifying item counts as a hit.
The current questions each identify one target quotation. Other relevant
passages can exist without receiving credit: these are intentionally incomplete
relevance judgments, not a complete relevance pool.

Hit@k and MRR@5 are averaged over 18 answerable questions. Four unanswerable
questions are excluded from that denominator and reported separately as the
rate of nonempty retrieval. This is not an answer-generation false-positive rate.
The evaluator checks that gold quotations still occur in the pinned corpus.
Tests independently check that each gold quotation fits some baseline chunk.
No answer generator sees these labels because no generator exists.

The deterministic report includes source-manifest, question-file, and chunk
hashes; no wall clock timestamps are mixed into it. CI reproduces its bytes.
Timings live in a separate machine-dependent file.

## Trust and future RAG boundary

Retrieved documents are data, not agent instructions. This code neither follows
links nor runs embedded code. A future generator must explicitly separate
retrieved text from instructions and validate citations; the present baseline
does not claim to have solved prompt injection, answerability, or hallucination.
No personal data, credential, private repository, or paid API is part of this
corpus or runtime. No public HTTP server is started.
