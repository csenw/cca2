"""Provided distributed FAISS runtime for INFS3208 A2.

Students should read this file to understand the distribution mechanism, but they
are NOT required to modify it. The assessed FAISS logic lives in student_faiss.py.
"""
from __future__ import annotations

import io
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import numpy as np
import requests

DEFAULT_MAX_SHARDS = int(os.getenv("FAISS_MAX_SHARDS", "3"))
DEFAULT_SERVICE = os.getenv("FAISS_SERVICE", "faiss-headless")
DEFAULT_PORT = int(os.getenv("FAISS_PORT", "8000"))
DEFAULT_TIMEOUT = float(os.getenv("FAISS_TIMEOUT", "5"))


def _shard_url(ordinal: int, service: str = DEFAULT_SERVICE, port: int = DEFAULT_PORT) -> str:
    # StatefulSet pod DNS: <pod-name>.<headless-service>
    return f"http://faiss-shard-{ordinal}.{service}:{port}"


def discover_shards(
    max_shards: int = DEFAULT_MAX_SHARDS,
    service: str = DEFAULT_SERVICE,
    port: int = DEFAULT_PORT,
    timeout: float = 0.8,
) -> list[str]:
    """Return reachable shard URLs.

    This intentionally probes predictable StatefulSet DNS names so the same
    notebook supports the cost-saving 1-replica mode and the required 3-replica
    final configuration without requiring Kubernetes API permissions.
    """
    reachable: list[str] = []
    for ordinal in range(max_shards):
        url = _shard_url(ordinal, service=service, port=port)
        try:
            r = requests.get(f"{url}/health", timeout=timeout)
            if r.ok:
                reachable.append(url)
        except requests.RequestException:
            pass
    if not reachable:
        raise RuntimeError(
            "No FAISS shard is reachable. Check the StatefulSet, headless Service, "
            "Pod readiness, and the faiss-config values."
        )
    return reachable


def publish_student_code(
    code_path: str | os.PathLike = "student_faiss.py",
    *,
    shards: list[str] | None = None,
) -> dict:
    """Send the student's FAISS implementation to each reachable shard."""
    code = Path(code_path).read_text(encoding="utf-8")
    shards = shards or discover_shards()
    results = {}
    for url in shards:
        r = requests.post(f"{url}/code", json={"source": code}, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        results[url] = r.json()
    return results


def partition_document_ids(doc_ids: np.ndarray, shard_count: int) -> list[np.ndarray]:
    """Return row-index arrays using the assignment's stable modulo partition rule."""
    doc_ids = np.asarray(doc_ids)
    if doc_ids.ndim != 1:
        raise ValueError("doc_ids must be a one-dimensional array")
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    return [np.flatnonzero((doc_ids % shard_count) == shard_id) for shard_id in range(shard_count)]


def _encode_index_payload(vectors: np.ndarray, doc_ids: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.savez_compressed(buf, vectors=np.asarray(vectors), doc_ids=np.asarray(doc_ids))
    return buf.getvalue()


def distributed_index(
    embeddings: np.ndarray,
    doc_ids: Iterable[int],
    *,
    shards: list[str] | None = None,
) -> dict:
    """Partition vectors and invoke the student's build_index() on every shard."""
    vectors = np.asarray(embeddings)
    ids = np.asarray(list(doc_ids), dtype=np.int64)
    if vectors.ndim != 2:
        raise ValueError("embeddings must have shape [num_documents, dimension]")
    if len(vectors) != len(ids):
        raise ValueError("embeddings and doc_ids must have the same number of rows")

    shards = shards or discover_shards()
    partitions = partition_document_ids(ids, len(shards))

    def send(url: str, row_ids: np.ndarray):
        payload = _encode_index_payload(vectors[row_ids], ids[row_ids])
        r = requests.post(
            f"{url}/index",
            data=payload,
            headers={"Content-Type": "application/octet-stream"},
            timeout=max(DEFAULT_TIMEOUT, 60),
        )
        r.raise_for_status()
        return r.json()

    summary: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(shards)) as pool:
        futures = {
            pool.submit(send, url, partitions[i]): url
            for i, url in enumerate(shards)
        }
        for future in as_completed(futures):
            url = futures[future]
            summary[url] = future.result()
    return {
        "num_shards": len(shards),
        "total_vectors": int(len(ids)),
        "shards": summary,
    }


def merge_top_k(shard_results: list[dict], k: int) -> list[dict]:
    """Merge local inner-product/cosine results into a global descending Top-K."""
    candidates: list[dict] = []
    for response in shard_results:
        candidates.extend(response.get("results", []))
    candidates.sort(key=lambda item: float(item["score"]), reverse=True)
    return candidates[:k]


def distributed_search(
    query_vector: np.ndarray,
    k: int = 5,
    *,
    shards: list[str] | None = None,
) -> dict:
    """Fan out one query to all shards, then merge local results globally."""
    query = np.asarray(query_vector)
    if query.ndim == 1:
        query = query.reshape(1, -1)
    if query.ndim != 2 or query.shape[0] != 1:
        raise ValueError("query_vector must have shape [dimension] or [1, dimension]")
    if k < 1:
        raise ValueError("k must be at least 1")

    shards = shards or discover_shards()
    payload = {"query": query[0].tolist(), "k": int(k)}

    def search(url: str):
        r = requests.post(f"{url}/search", json=payload, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()

    local: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(shards)) as pool:
        futures = {pool.submit(search, url): url for url in shards}
        for future in as_completed(futures):
            local.append(future.result())

    return {
        "num_shards": len(shards),
        "local_results": local,
        "global_top_k": merge_top_k(local, k),
    }


def shard_status(shards: list[str] | None = None) -> dict:
    shards = shards or discover_shards()
    status = {}
    for url in shards:
        r = requests.get(f"{url}/status", timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        status[url] = r.json()
    return status
