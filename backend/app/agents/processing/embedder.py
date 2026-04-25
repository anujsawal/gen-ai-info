from fastembed import TextEmbedding
from langchain.text_splitter import RecursiveCharacterTextSplitter
from functools import lru_cache
import numpy as np
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def _get_model() -> TextEmbedding:
    logger.info("loading_embedding_model", model=settings.embedding_model)
    return TextEmbedding(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    prefixed = [f"search_document: {t}" for t in texts]
    embeddings = list(model.embed(prefixed))
    return [e.tolist() for e in embeddings]


def embed_query(query: str) -> list[float]:
    model = _get_model()
    embeddings = list(model.embed([f"search_query: {query}"]))
    return embeddings[0].tolist()


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)
