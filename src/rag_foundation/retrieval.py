"""Original, transparent BM25 implementation over an inverted index."""

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re

from .corpus import Chunk, _positive_int

# Version this policy before any future change. No stemming or cross-language model.
TOKENIZER = "unicode-word-casefold-v1"


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float

    def to_dict(self) -> dict:
        return {"chunk_id": self.chunk.id, "document_id": self.chunk.document_id,
                "score": self.score, "citation": self.chunk.citation,
                "text": self.chunk.text}


class BM25:
    """Positive Robertson IDF, unique query terms, no title or field boosting.

    idf = log(1 + (N - df + 0.5) / (df + 0.5))
    term = idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg_length))
    A nonzero score is lexical evidence only, not answerability or confidence.
    """

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        if (isinstance(k1, bool) or isinstance(b, bool) or not math.isfinite(k1)
                or not math.isfinite(b) or k1 <= 0 or not 0 <= b <= 1):
            raise ValueError("BM25 requires finite k1 > 0 and 0 <= b <= 1")
        if len({c.id for c in chunks}) != len(chunks):
            raise ValueError("duplicate chunk IDs")
        self.chunks = tuple(chunks)
        self.k1, self.b = k1, b
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.lengths = []
        for i, chunk in enumerate(chunks):
            terms = Counter(tokenize(chunk.text))
            self.lengths.append(sum(terms.values()))
            for token, tf in terms.items():
                self.postings[token].append((i, tf))
        self.avg_length = sum(self.lengths) / len(chunks) if chunks else 0

    def search(self, query: str, k: int = 5) -> list[SearchHit]:
        _positive_int(k, "k")
        scores: dict[int, float] = defaultdict(float)
        if not self.avg_length:
            return []
        for token in sorted(set(tokenize(query))):
            postings = self.postings.get(token, [])
            df = len(postings)
            if not df:
                continue
            idf = math.log1p((len(self.chunks) - df + 0.5) / (df + 0.5))
            for i, tf in postings:
                normalizer = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_length)
                scores[i] += idf * tf * (self.k1 + 1) / (tf + normalizer)
        order = sorted(scores, key=lambda i: (-scores[i], self.chunks[i].id))[:k]
        return [SearchHit(self.chunks[i], scores[i]) for i in order]
