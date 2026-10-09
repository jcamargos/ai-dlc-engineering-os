from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable

from ._store_base import MemoryHit, _flags, utcnow
from .security import MEMORY_KINDS, ValidationError

DEFAULT_DIMENSIONS = 384


def local_embedding(text: str, dimensions: int = DEFAULT_DIMENSIONS) -> list[float]:
    """Dependency-free feature hashing for private, deterministic local retrieval.

    This is intentionally labelled ``agentshield-local-v1`` rather than presented as
    a neural embedding model. Callers can supply provider embeddings for higher recall.
    """
    if dimensions < 32 or dimensions > 4096:
        raise ValueError("dimensions must be between 32 and 4096")
    vector = [0.0] * dimensions
    tokens = re.findall(r"[\w.-]+", (text or "").lower(), flags=re.UNICODE)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        vector[bucket] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = list(left), list(right)
    if len(a) != len(b):
        raise ValueError("embedding dimensions do not match")
    denominator = math.sqrt(sum(v * v for v in a)) * math.sqrt(sum(v * v for v in b))
    return 0.0 if denominator == 0 else sum(x * y for x, y in zip(a, b, strict=True)) / denominator


class VectorMemoryMixin:
    def index_memory(
        self,
        memory_id: str,
        embedding: list[float] | None = None,
        *,
        model: str = "agentshield-local-v1",
        source_system: str = "agentshield",
        external_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            memory = conn.execute(
                "SELECT * FROM memories WHERE id=? AND workspace_id=? AND status='active'",
                (memory_id, self.workspace_id),
            ).fetchone()
            if not memory:
                raise KeyError(f"Memory not found: {memory_id}")
            content = f"{memory['kind']} {memory['title']} {memory['content']} {memory['tags_json']}"
            vector = embedding if embedding is not None else local_embedding(content)
            if not vector or len(vector) > 4096 or any(not math.isfinite(float(v)) for v in vector):
                raise ValueError("embedding must contain 1..4096 finite numbers")
            vector = [float(v) for v in vector]
            now = utcnow()
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            conn.execute(
                """INSERT INTO memory_embeddings(memory_id,workspace_id,model,dimensions,vector_json,source_system,external_id,content_hash,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(memory_id) DO UPDATE SET model=excluded.model, dimensions=excluded.dimensions,
                   vector_json=excluded.vector_json, source_system=excluded.source_system, external_id=excluded.external_id,
                   content_hash=excluded.content_hash, updated_at=excluded.updated_at""",
                (memory_id, self.workspace_id, model, len(vector), json.dumps(vector), source_system, external_id, content_hash, now, now),
            )
            self._audit(conn, "memory.indexed", "memory", memory_id, {"model": model, "dimensions": len(vector), "source_system": source_system})
            return {"memory_id": memory_id, "model": model, "dimensions": len(vector), "content_hash": content_hash}

    def semantic_search(
        self,
        query: str,
        project_id: str | None = None,
        limit: int = 8,
        embedding: list[float] | None = None,
        model: str = "agentshield-local-v1",
    ) -> list[MemoryHit]:
        project_id = self._pid(project_id, required=False)
        query_vector = embedding if embedding is not None else local_embedding(query)
        with self._connect() as conn:
            params: list[Any] = [self.workspace_id]
            project_filter = ""
            if project_id:
                project_filter = " AND (m.project_id=? OR m.project_id IS NULL)"
                params.append(project_id)
            rows = conn.execute(
                """SELECT m.*, e.vector_json, e.model FROM memories m
                   JOIN memory_embeddings e ON e.memory_id=m.id
                   WHERE m.workspace_id=? AND m.status='active'""" + project_filter + " LIMIT 2000",
                params,
            ).fetchall()
        hits: list[MemoryHit] = []
        for row in rows:
            stored = json.loads(row["vector_json"])
            if len(stored) != len(query_vector):
                continue
            score = cosine_similarity(query_vector, stored)
            hits.append(MemoryHit("memory", row["id"], row["title"], row["content"], row["project_id"], score, {"kind": row["kind"], "model": row["model"], "flags": _flags(row)}))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: max(1, min(int(limit), 50))]

    def bridge_native_memories(self, source_system: str, records: list[dict[str, Any]], project_id: str | None = None) -> dict[str, Any]:
        if source_system not in {"claude", "codex", "agentshield"}:
            raise ValueError("source_system must be claude, codex, or agentshield")
        imported: list[str] = []
        skipped = 0
        refused: list[dict[str, str]] = []
        for record in records[:1000]:
            external_id = str(record.get("id") or "").strip()
            content = str(record.get("content") or "").strip()
            if not external_id or not content:
                skipped += 1
                continue
            with self._connect() as conn:
                existing = conn.execute(
                    "SELECT memory_id FROM memory_embeddings WHERE workspace_id=? AND source_system=? AND external_id=?",
                    (self.workspace_id, source_system, external_id),
                ).fetchone()
            if existing:
                skipped += 1
                continue
            kind = str(record.get("kind") or "other").lower()
            tags = record.get("tags") or [source_system]
            try:
                memory = self.save_memory(
                project_id,
                kind if kind in MEMORY_KINDS else "other",
                str(record.get("title") or f"{source_system}:{external_id}"),
                content,
                list(tags) if isinstance(tags, (list, tuple)) else [str(tags)],
                float(record.get("confidence", 0.8)),
                str(record.get("evidence") or ""),
                source_system,
                )
            except (ValidationError, ValueError) as exc:
                refused.append({"external_id": external_id[:120], "reason": str(exc)[:300]})
                continue
            self.index_memory(memory["id"], record.get("embedding"), model=str(record.get("model") or "agentshield-local-v1"), source_system=source_system, external_id=external_id)
            imported.append(memory["id"])
        return {"source_system": source_system, "imported": len(imported), "skipped": skipped, "refused": refused, "memory_ids": imported}
