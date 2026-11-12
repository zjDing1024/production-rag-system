"""Checksum-verified document ingestion and deterministic source-span chunks."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _positive_int(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _within(root: Path, relative: str) -> Path:
    """Do not let a manifest read outside its explicit corpus root."""
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("manifest paths must be relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("manifest path escapes the corpus root")
    return path


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str
    source_url: str
    sha256: str
    license: str


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    title: str
    text: str
    source_url: str
    source_sha256: str
    license: str
    start_char: int
    end_char: int
    start_line: int
    end_line: int

    @property
    def citation(self) -> str:
        return f"{self.source_url}#L{self.start_line}-L{self.end_line}"


def load_corpus(root: Path, manifest_path: Path | None = None) -> list[Document]:
    manifest_path = manifest_path or root / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported corpus schema")
    license_bytes = _within(root, manifest["license_path"]).read_bytes()
    if digest(license_bytes) != manifest["license_sha256"]:
        raise ValueError("license checksum mismatch")
    documents = []
    ids = set()
    for row in manifest["documents"]:
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in ids:
            raise ValueError("document IDs must be nonempty and unique")
        ids.add(row["id"])
        content = _within(root, row["path"]).read_bytes()
        if digest(content) != row["sha256"] or len(content) != row["size_bytes"]:
            raise ValueError(f"source checksum or size mismatch: {row['id']}")
        if row["license"] != "BSD-3-Clause":
            raise ValueError("this manifest supports only the reviewed BSD-3-Clause corpus")
        if not row["source_url"].startswith("https://github.com/pallets/flask/blob/"):
            raise ValueError("unexpected source URL")
        documents.append(Document(row["id"], row["title"], content.decode("utf-8"),
                                  row["source_url"], row["sha256"], row["license"]))
    if not documents:
        raise ValueError("corpus is empty")
    return sorted(documents, key=lambda doc: doc.id)


def chunk_document(document: Document, max_words: int = 180, overlap: int = 40) -> list[Chunk]:
    """Overlapping whitespace-word windows. RST stays intact; not model tokens.

    Each text is an exact character slice of the original UTF-8-decoded source.
    Character offsets are half-open, and source line numbers are 1-based inclusive.
    No parsing, rendering, fetching linked documents, or execution of source code.
    """
    _positive_int(max_words, "max_words")
    if type(overlap) is not int or not 0 <= overlap < max_words:
        raise ValueError("overlap must satisfy 0 <= overlap < max_words")
    words = list(re.finditer(r"\S+", document.text))
    chunks = []
    for start in range(0, len(words), max_words - overlap):
        end = min(start + max_words, len(words))
        a, b = words[start].start(), words[end - 1].end()
        text = document.text[a:b]
        identity = f"{document.id}\0{document.sha256}\0{a}\0{b}".encode()
        chunks.append(Chunk(
            id=digest(identity), document_id=document.id, title=document.title, text=text,
            source_url=document.source_url, source_sha256=document.sha256,
            license=document.license, start_char=a, end_char=b,
            start_line=document.text.count("\n", 0, a) + 1,
            end_line=document.text.count("\n", 0, b) + 1,
        ))
        if end == len(words):
            break
    return chunks


def build_chunks(documents: list[Document], max_words: int = 180, overlap: int = 40) -> list[Chunk]:
    _positive_int(max_words, "max_words")
    if type(overlap) is not int or not 0 <= overlap < max_words:
        raise ValueError("overlap must satisfy 0 <= overlap < max_words")
    if len({doc.id for doc in documents}) != len(documents):
        raise ValueError("duplicate document IDs")
    return [chunk for doc in sorted(documents, key=lambda doc: doc.id)
            for chunk in chunk_document(doc, max_words, overlap)]


def write_chunks(chunks: list[Chunk], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(asdict(c), ensure_ascii=False, sort_keys=True) + "\n"
                              for c in chunks), encoding="utf-8")


def read_chunks(path: Path) -> list[Chunk]:
    chunks = []
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        chunk = Chunk(**json.loads(line))
        if chunk.id in ids or not chunk.id or not isinstance(chunk.text, str):
            raise ValueError("invalid or duplicate chunk")
        if not 0 <= chunk.start_char < chunk.end_char:
            raise ValueError("invalid character span")
        if not 1 <= chunk.start_line <= chunk.end_line:
            raise ValueError("invalid line span")
        ids.add(chunk.id)
        chunks.append(chunk)
    return chunks
