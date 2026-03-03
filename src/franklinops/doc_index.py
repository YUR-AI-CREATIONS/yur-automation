from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .audit import AuditLogger
from .opsdb import OpsDB


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def chunk_text(text: str, *, max_chars: int = 1400, overlap: int = 200) -> list[str]:
    t = (text or "").replace("\r\n", "\n").strip()
    if not t:
        return []

    chunks: list[str] = []
    start = 0
    n = len(t)
    while start < n:
        end = min(n, start + max_chars)
        cut = t.rfind("\n", start, end)
        if cut != -1 and cut > start + int(max_chars * 0.6):
            end = cut
        chunk = t[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, end) if overlap > 0 else end
    return chunks


class EmbeddingsBackend:
    dimension: int
    name: str

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class HashEmbeddings(EmbeddingsBackend):
    def __init__(self, dimension: int = 384):
        self.dimension = int(dimension)
        self.name = f"hash:{self.dimension}"

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = (text or "").lower().split()
            for tok in tokens:
                tok = tok.strip()
                if not tok:
                    continue
                d = hashlib.blake2b(tok.encode("utf-8", errors="ignore"), digest_size=8).digest()
                idx = int.from_bytes(d[:4], "little") % self.dimension
                sign = 1.0 if (d[4] & 1) else -1.0
                vecs[i, idx] += sign
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vecs = vecs / norms
        return vecs.astype(np.float32)


class SentenceTransformerEmbeddings(EmbeddingsBackend):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(model_name)
        self.name = f"sentence-transformers:{model_name}"
        # SentenceTransformer doesn't expose dim reliably across backends; infer on first embed.
        probe = self._model.encode(["dimension probe"])
        self.dimension = int(np.asarray(probe).shape[-1])

    def embed(self, texts: list[str]) -> np.ndarray:
        emb = self._model.encode(texts, show_progress_bar=False)
        return np.asarray(emb, dtype=np.float32)


def build_embeddings_backend(preferred: str) -> EmbeddingsBackend:
    if preferred.startswith("sentence-transformers:"):
        model_name = preferred.split(":", 1)[1]
        try:
            return SentenceTransformerEmbeddings(model_name)
        except Exception:
            return HashEmbeddings(384)
    if preferred.startswith("hash:"):
        try:
            dim = int(preferred.split(":", 1)[1])
        except Exception:
            dim = 384
        return HashEmbeddings(dim)
    return HashEmbeddings(384)


@dataclass(frozen=True)
class DocIndexPaths:
    index_faiss_path: Path
    vectors_npz_path: Path
    meta_json_path: Path


def default_index_paths(data_dir: Path) -> DocIndexPaths:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return DocIndexPaths(
        index_faiss_path=data_dir / "doc_index.faiss",
        vectors_npz_path=data_dir / "doc_index_vectors.npz",
        meta_json_path=data_dir / "doc_index_meta.json",
    )


def _try_import_faiss() -> Any:
    try:
        import faiss  # type: ignore

        return faiss
    except Exception:
        return None


def rebuild_doc_index(
    db: OpsDB,
    audit: AuditLogger,
    *,
    data_dir: Path,
    embeddings_preference: str = "sentence-transformers:all-MiniLM-L6-v2",
    chunk_max_chars: int = 1400,
    chunk_overlap: int = 200,
) -> dict[str, Any]:
    paths = default_index_paths(data_dir)

    # 1) Load artifacts to index
    artifact_rows = db.conn.execute(
        """
        SELECT id, source, path, birthmark, extracted_text
        FROM artifacts
        WHERE status = 'ingested' AND extracted_text IS NOT NULL AND extracted_text != ''
        ORDER BY ingested_at DESC
        """
    ).fetchall()

    # 2) Chunk + persist doc_chunks
    chunks_meta: list[dict[str, Any]] = []
    chunks_text: list[str] = []

    with db.tx() as conn:
        conn.execute("DELETE FROM doc_chunks")

        for art in artifact_rows:
            art_id = art["id"]
            source = art["source"]
            rel_path = art["path"]
            birthmark = art["birthmark"] or ""
            text = art["extracted_text"] or ""

            pieces = chunk_text(text, max_chars=chunk_max_chars, overlap=chunk_overlap)
            for idx, piece in enumerate(pieces):
                chunk_id = hashlib.sha256(f"{art_id}:{idx}:{birthmark}".encode("utf-8")).hexdigest()[:32]
                now = utcnow_iso()
                conn.execute(
                    """
                    INSERT INTO doc_chunks (id, artifact_id, chunk_index, text, birthmark, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chunk_id, art_id, idx, piece, birthmark, now, now),
                )

                chunks_meta.append(
                    {
                        "chunk_id": chunk_id,
                        "artifact_id": art_id,
                        "source": source,
                        "path": rel_path,
                        "birthmark": birthmark,
                        "chunk_index": idx,
                    }
                )
                chunks_text.append(piece)

    # 3) Embed
    backend = build_embeddings_backend(embeddings_preference)
    vectors = backend.embed(chunks_text) if chunks_text else np.zeros((0, backend.dimension), dtype=np.float32)

    # 4) Save vectors for numpy fallback
    np.savez_compressed(paths.vectors_npz_path, vectors=vectors)

    # 5) Build FAISS index if possible
    faiss = _try_import_faiss()
    index_backend = "numpy"
    if faiss is not None and vectors.shape[0] > 0:
        try:
            index = faiss.IndexFlatL2(int(vectors.shape[1]))
            index.add(vectors.astype("float32"))
            faiss.write_index(index, str(paths.index_faiss_path))
            index_backend = "faiss"
        except Exception:
            index_backend = "numpy"

    # 6) Save meta (includes embedding backend choice)
    meta = {
        "version": 1,
        "created_at": utcnow_iso(),
        "embeddings_backend": backend.name,
        "index_backend": index_backend,
        "dimension": int(vectors.shape[1]) if vectors.ndim == 2 else backend.dimension,
        "chunks": chunks_meta,
        "paths": {
            "index_faiss_path": str(paths.index_faiss_path),
            "vectors_npz_path": str(paths.vectors_npz_path),
            "meta_json_path": str(paths.meta_json_path),
        },
    }
    paths.meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 7) Persist run record
    run_id = hashlib.sha256(f"{meta['created_at']}:{len(chunks_meta)}".encode("utf-8")).hexdigest()[:24]
    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO doc_index_runs (
              id, created_at, embeddings_backend, index_backend,
              artifacts_indexed, chunks_indexed, index_path, meta_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                meta["created_at"],
                backend.name,
                index_backend,
                int(len(artifact_rows)),
                int(len(chunks_meta)),
                str(paths.index_faiss_path),
                str(paths.meta_json_path),
            ),
        )

    audit.append(
        actor="system",
        action="doc_index_rebuilt",
        scope="internal",
        details={
            "artifacts_indexed": int(len(artifact_rows)),
            "chunks_indexed": int(len(chunks_meta)),
            "embeddings_backend": backend.name,
            "index_backend": index_backend,
        },
    )

    return {
        "run_id": run_id,
        "artifacts_indexed": int(len(artifact_rows)),
        "chunks_indexed": int(len(chunks_meta)),
        "embeddings_backend": backend.name,
        "index_backend": index_backend,
        "paths": meta["paths"],
    }


def load_doc_index_meta(meta_path: Path) -> dict[str, Any]:
    return json.loads(Path(meta_path).read_text(encoding="utf-8"))


def _load_vectors(vectors_npz_path: Path) -> np.ndarray:
    data = np.load(str(vectors_npz_path))
    return np.asarray(data["vectors"], dtype=np.float32)


def search_doc_index(
    db: OpsDB,
    *,
    data_dir: Path,
    query: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    paths = default_index_paths(data_dir)
    if not paths.meta_json_path.exists() or not paths.vectors_npz_path.exists():
        raise FileNotFoundError("doc index not built yet")

    meta = load_doc_index_meta(paths.meta_json_path)
    vectors = _load_vectors(paths.vectors_npz_path)
    backend = build_embeddings_backend(meta.get("embeddings_backend", "hash:384"))

    qv = backend.embed([query]).astype(np.float32)
    if vectors.shape[0] == 0:
        return []

    # Prefer FAISS if available and index exists
    faiss = _try_import_faiss()
    indices: np.ndarray
    distances: np.ndarray
    if faiss is not None and Path(meta.get("paths", {}).get("index_faiss_path", "")).exists():
        try:
            index = faiss.read_index(str(paths.index_faiss_path))
            distances, indices = index.search(qv, int(k))
            indices = np.asarray(indices[0], dtype=np.int64)
            distances = np.asarray(distances[0], dtype=np.float32)
        except Exception:
            faiss = None

    if faiss is None:
        diff = vectors - qv[0]
        distances = np.sum(diff * diff, axis=1).astype(np.float32)
        indices = np.argsort(distances)[: int(k)].astype(np.int64)
        distances = distances[indices]

    chunks = meta.get("chunks", [])
    hits: list[dict[str, Any]] = []
    for rank, (idx, dist) in enumerate(zip(indices.tolist(), distances.tolist()), start=1):
        if idx < 0 or idx >= len(chunks):
            continue
        cm = chunks[idx]
        chunk_id = cm["chunk_id"]
        row = db.conn.execute(
            """
            SELECT text FROM doc_chunks WHERE id = ?
            """,
            (chunk_id,),
        ).fetchone()
        text = (row["text"] if row else "") or ""
        hits.append(
            {
                "rank": rank,
                "distance": float(dist),
                "similarity": float(1.0 / (1.0 + float(dist))),
                "chunk": {**cm, "text": text},
            }
        )
    return hits

