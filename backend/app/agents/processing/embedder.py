from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from functools import lru_cache
from typing import Optional
import numpy as np
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    logger.info("loading_embedding_model", model=settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model, trust_remote_code=True)
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns list of float vectors."""
    model = _get_model()
    # nomic-embed-text requires a task prefix
    prefixed = [f"search_document: {t}" for t in texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a search query (different prefix for nomic-embed-text)."""
    model = _get_model()
    embedding = model.encode(f"search_query: {query}", normalize_embeddings=True)
    return embedding.tolist()


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping chunks for RAG."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)
