import numpy as np
from sklearn.preprocessing import normalize
try:
    import hdbscan
    HAS_HDBSCAN = True
except ImportError:
    HAS_HDBSCAN = False
from sklearn.cluster import KMeans
from typing import Optional
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def cluster_articles(
    embeddings: list[list[float]],
    article_ids: list[str],
    min_cluster_size: Optional[int] = None,
) -> dict[str, list[str]]:
    """
    Cluster article embeddings using HDBSCAN (or KMeans fallback).
    Returns: {cluster_id -> [article_id, ...]}
    Noise points (HDBSCAN label -1) each form their own singleton cluster.
    """
    if len(embeddings) < 2:
        return {"cluster_0": article_ids}

    min_size = min_cluster_size or settings.cluster_min_size
    X = normalize(np.array(embeddings, dtype=np.float32))

    labels = _run_hdbscan(X, min_size) if HAS_HDBSCAN else _run_kmeans(X, len(embeddings))

    clusters: dict[str, list[str]] = {}
    for article_id, label in zip(article_ids, labels):
        if label == -1:
            key = f"noise_{article_id}"  # each noise point is its own cluster
        else:
            key = f"cluster_{label}"
        clusters.setdefault(key, []).append(article_id)

    logger.info("clustering_done", n_articles=len(article_ids), n_clusters=len(clusters))
    return clusters


def _run_hdbscan(X: np.ndarray, min_cluster_size: int) -> list[int]:
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",   # cosine-normalized vectors → euclidean = cosine
        cluster_selection_method="eom",
    )
    return clusterer.fit_predict(X).tolist()


def _run_kmeans(X: np.ndarray, n_articles: int) -> list[int]:
    n_clusters = max(2, n_articles // 3)
    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    return km.fit_predict(X).tolist()


def find_representative(embeddings: list[list[float]], article_ids: list[str]) -> str:
    """Find the article closest to the centroid of its cluster."""
    if len(article_ids) == 1:
        return article_ids[0]
    X = np.array(embeddings, dtype=np.float32)
    centroid = X.mean(axis=0)
    distances = np.linalg.norm(X - centroid, axis=1)
    return article_ids[int(np.argmin(distances))]


def compute_centroid(embeddings: list[list[float]]) -> list[float]:
    X = normalize(np.array(embeddings, dtype=np.float32))
    return X.mean(axis=0).tolist()
