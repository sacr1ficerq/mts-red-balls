"""
Semantic RAG (Retrieval-Augmented Generation) using sentence-transformers + FAISS.

Architecture:
- Documents are split into chunks with overlap
- Each chunk is embedded using sentence-transformers (local model, no API needed)
- FAISS index enables fast cosine similarity search
- Knowledge base is auto-loaded from backend/kaggle_solver/knowledge/*.md on first use
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports — sentence-transformers and faiss are optional heavy deps
# ---------------------------------------------------------------------------

_EMBED_MODEL = None
_EMBED_LOCK = threading.Lock()
_FAISS_AVAILABLE = False
_ST_AVAILABLE = False

try:
    import faiss  # noqa: F401
    _FAISS_AVAILABLE = True
except ImportError:
    logger.warning("faiss-cpu not installed. Falling back to numpy cosine search.")

try:
    from sentence_transformers import SentenceTransformer  # noqa: F401
    _ST_AVAILABLE = True
except ImportError:
    logger.warning("sentence-transformers not installed. RAG will use keyword fallback.")


def _get_embed_model() -> Optional[Any]:
    """Lazy-load the embedding model (thread-safe singleton)."""
    global _EMBED_MODEL
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    if not _ST_AVAILABLE:
        return None
    with _EMBED_LOCK:
        if _EMBED_MODEL is None:
            try:
                from sentence_transformers import SentenceTransformer
                # all-MiniLM-L6-v2: 384-dim, fast, good quality, ~80MB
                logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
                _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Embedding model loaded.")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
    return _EMBED_MODEL


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class Document:
    """A source document with content and metadata."""

    def __init__(self, content: str, metadata: Dict[str, Any] = None):
        self.content = content
        self.metadata = metadata or {}


class Chunk:
    """A text chunk derived from a document."""

    def __init__(self, content: str, document_id: str, chunk_index: int,
                 metadata: Dict[str, Any] = None):
        self.content = content
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.metadata = metadata or {}


# ---------------------------------------------------------------------------
# Core RAG class
# ---------------------------------------------------------------------------

class RAG:
    """
    Semantic RAG with sentence-transformer embeddings and FAISS index.

    Falls back to numpy cosine search if faiss is unavailable.
    Falls back to keyword overlap if sentence-transformers is unavailable.
    """

    KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

    def __init__(self, chunk_size: int = 512, overlap: int = 64, llm=None):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.llm = llm

        self.documents: Dict[str, Document] = {}
        self.chunks: List[Chunk] = []

        # Embedding matrix (n_chunks × embed_dim) — numpy float32
        self._embeddings: Optional[np.ndarray] = None
        # FAISS index (if available)
        self._faiss_index = None

        self._index_dirty = False  # True when chunks added but index not rebuilt
        self._kb_loaded = False    # True after knowledge base auto-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_document(self, doc_id: str, content: str, metadata: Dict = None):
        """Add a document and update the index."""
        self.documents[doc_id] = Document(content, metadata)
        new_chunks = self._chunk_text(content, doc_id, metadata)
        self.chunks.extend(new_chunks)
        self._index_dirty = True
        logger.debug(f"Added document '{doc_id}' → {len(new_chunks)} chunks")

    def search(self, query: str, top_k: int = 5,
               category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Semantic search over all chunks.

        Args:
            query: Natural language query.
            top_k: Number of results to return.
            category: Optional metadata category filter (e.g. 'feature_engineering').

        Returns:
            List of dicts with keys: content, document_id, score, metadata.
        """
        self._ensure_kb_loaded()
        if not self.chunks:
            return []

        self._rebuild_index_if_needed()

        model = _get_embed_model()
        if model is not None:
            return self._semantic_search(query, top_k, category, model)
        else:
            return self._keyword_search(query, top_k, category)

    def get_context(self, query: str, max_chars: int = 3000,
                    top_k: int = 8, category: Optional[str] = None) -> str:
        """
        Retrieve relevant context for a query, formatted as a string.

        Args:
            query: The question or task description.
            max_chars: Maximum total characters to return.
            top_k: Number of chunks to retrieve.
            category: Optional category filter.

        Returns:
            Formatted context string with source annotations.
        """
        results = self.search(query, top_k=top_k, category=category)
        if not results:
            return ""

        parts: List[str] = []
        total = 0
        seen_docs: set = set()

        for r in results:
            doc_id = r["document_id"]
            content = r["content"].strip()
            score = r["score"]

            # Deduplicate by document for diversity
            doc_label = doc_id.replace(".md", "").replace("_", " ").title()
            header = f"[{doc_label} | relevance: {score:.2f}]"
            block = f"{header}\n{content}"

            if total + len(block) > max_chars:
                # Try to fit a truncated version
                remaining = max_chars - total - len(header) - 5
                if remaining > 100:
                    block = f"{header}\n{content[:remaining]}..."
                else:
                    break

            parts.append(block)
            total += len(block)
            seen_docs.add(doc_id)

        return "\n\n---\n\n".join(parts)

    def answer(self, query: str, context: str = None) -> str:
        """Generate an answer using retrieved context + LLM."""
        if context is None:
            context = self.get_context(query)

        if not context:
            return "No relevant information found in knowledge base."

        if self.llm is None:
            return f"**Retrieved Context:**\n\n{context}\n\n**Query:** {query}"

        prompt = (
            "You are a Kaggle expert. Use the following knowledge base excerpts to "
            "answer the question. Be specific and practical.\n\n"
            f"Knowledge Base:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.llm.generate(prompt=prompt, max_tokens=800))
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(self.llm.generate(prompt=prompt, max_tokens=800))
        except Exception as e:
            logger.error(f"RAG answer error: {e}")
            return f"Context found:\n\n{context}"

    def load_documents_from_directory(self, directory: Path,
                                       file_patterns: List[str] = None):
        """Load all matching files from a directory as documents."""
        if file_patterns is None:
            file_patterns = ["*.txt", "*.md", "*.py", "*.json"]

        loaded = 0
        for pattern in file_patterns:
            for file_path in sorted(directory.rglob(pattern)):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if not content.strip():
                        continue
                    doc_id = str(file_path.relative_to(directory))
                    # Extract category from filename
                    category = file_path.stem  # e.g. "feature_engineering"
                    self.add_document(doc_id, content, {
                        "source": str(file_path),
                        "category": category,
                        "filename": file_path.name,
                    })
                    loaded += 1
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")

        logger.info(f"Loaded {loaded} documents from {directory}")
        return loaded

    def clear(self):
        """Clear all documents, chunks, and index."""
        self.documents.clear()
        self.chunks.clear()
        self._embeddings = None
        self._faiss_index = None
        self._index_dirty = False
        self._kb_loaded = False

    def stats(self) -> Dict[str, Any]:
        """Return statistics about the knowledge base."""
        return {
            "documents": len(self.documents),
            "chunks": len(self.chunks),
            "has_embeddings": self._embeddings is not None,
            "has_faiss": self._faiss_index is not None,
            "semantic_search": _ST_AVAILABLE,
            "kb_loaded": self._kb_loaded,
        }

    # ------------------------------------------------------------------
    # Internal: knowledge base auto-loading
    # ------------------------------------------------------------------

    def _ensure_kb_loaded(self):
        """Auto-load the built-in knowledge base on first use."""
        if self._kb_loaded:
            return
        self._kb_loaded = True  # Set before loading to prevent recursion

        if self.KNOWLEDGE_DIR.exists():
            n = self.load_documents_from_directory(self.KNOWLEDGE_DIR, ["*.md"])
            if n > 0:
                logger.info(f"Auto-loaded {n} knowledge base documents from {self.KNOWLEDGE_DIR}")
        else:
            logger.warning(f"Knowledge directory not found: {self.KNOWLEDGE_DIR}")

    # ------------------------------------------------------------------
    # Internal: chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str, doc_id: str,
                    metadata: Dict = None) -> List[Chunk]:
        """
        Split text into overlapping chunks, respecting paragraph/sentence boundaries.
        """
        # Split on double newlines (paragraphs) first, then sentences
        paragraphs = re.split(r'\n{2,}', text)
        chunks: List[Chunk] = []
        current = ""
        chunk_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 2 <= self.chunk_size:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(Chunk(current, doc_id, chunk_idx, metadata))
                    chunk_idx += 1
                    # Overlap: keep last `overlap` chars of current chunk
                    overlap_text = current[-self.overlap:] if len(current) > self.overlap else current
                    current = (overlap_text + "\n\n" + para).strip()
                else:
                    # Paragraph itself is too long — split by sentences
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    for sent in sentences:
                        if len(current) + len(sent) + 1 <= self.chunk_size:
                            current = (current + " " + sent).strip()
                        else:
                            if current:
                                chunks.append(Chunk(current, doc_id, chunk_idx, metadata))
                                chunk_idx += 1
                                overlap_text = current[-self.overlap:]
                                current = (overlap_text + " " + sent).strip()
                            else:
                                # Single sentence longer than chunk_size — keep as-is
                                chunks.append(Chunk(sent, doc_id, chunk_idx, metadata))
                                chunk_idx += 1

        if current.strip():
            chunks.append(Chunk(current.strip(), doc_id, chunk_idx, metadata))

        return chunks

    # ------------------------------------------------------------------
    # Internal: index management
    # ------------------------------------------------------------------

    def _rebuild_index_if_needed(self):
        """Rebuild embeddings and FAISS index if chunks changed."""
        if not self._index_dirty:
            return
        self._index_dirty = False

        model = _get_embed_model()
        if model is None:
            return  # Will use keyword fallback

        texts = [c.content for c in self.chunks]
        if not texts:
            return

        logger.debug(f"Building embeddings for {len(texts)} chunks...")
        try:
            embeddings = model.encode(
                texts,
                batch_size=64,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,  # L2-normalize for cosine via dot product
            )
            self._embeddings = embeddings.astype(np.float32)

            if _FAISS_AVAILABLE:
                import faiss
                dim = self._embeddings.shape[1]
                # IndexFlatIP = inner product on normalized vectors = cosine similarity
                index = faiss.IndexFlatIP(dim)
                index.add(self._embeddings)
                self._faiss_index = index
                logger.debug(f"FAISS index built: {index.ntotal} vectors, dim={dim}")
            else:
                self._faiss_index = None

        except Exception as e:
            logger.error(f"Failed to build embeddings: {e}")
            self._embeddings = None
            self._faiss_index = None

    # ------------------------------------------------------------------
    # Internal: search implementations
    # ------------------------------------------------------------------

    def _semantic_search(self, query: str, top_k: int,
                         category: Optional[str],
                         model) -> List[Dict[str, Any]]:
        """Semantic search using embeddings."""
        try:
            q_emb = model.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
            ).astype(np.float32)

            if self._faiss_index is not None:
                # FAISS search — returns (scores, indices)
                k = min(top_k * 3, len(self.chunks))  # Over-fetch for category filter
                scores, indices = self._faiss_index.search(q_emb, k)
                scores = scores[0]
                indices = indices[0]
            else:
                # Numpy fallback: dot product on normalized vectors = cosine
                scores_all = (self._embeddings @ q_emb.T).squeeze()
                k = min(top_k * 3, len(self.chunks))
                indices = np.argsort(scores_all)[::-1][:k]
                scores = scores_all[indices]

            results = []
            for score, idx in zip(scores, indices):
                if idx < 0 or idx >= len(self.chunks):
                    continue
                chunk = self.chunks[idx]
                # Category filter
                if category and chunk.metadata.get("category") != category:
                    continue
                results.append({
                    "content": chunk.content,
                    "document_id": chunk.document_id,
                    "score": float(score),
                    "metadata": chunk.metadata,
                })
                if len(results) >= top_k:
                    break

            return results

        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return self._keyword_search(query, top_k, category)

    def _keyword_search(self, query: str, top_k: int,
                        category: Optional[str]) -> List[Dict[str, Any]]:
        """
        Fallback keyword search using TF-IDF-like scoring.
        Better than simple word overlap — uses IDF weighting.
        """
        import math

        query_tokens = set(re.findall(r'\w+', query.lower()))
        if not query_tokens:
            return []

        # Compute IDF
        n_docs = len(self.chunks)
        df: Dict[str, int] = {}
        for chunk in self.chunks:
            chunk_tokens = set(re.findall(r'\w+', chunk.content.lower()))
            for t in query_tokens:
                if t in chunk_tokens:
                    df[t] = df.get(t, 0) + 1

        idf = {t: math.log((n_docs + 1) / (df.get(t, 0) + 1)) for t in query_tokens}

        results = []
        for chunk in self.chunks:
            if category and chunk.metadata.get("category") != category:
                continue
            chunk_tokens = re.findall(r'\w+', chunk.content.lower())
            chunk_token_set = set(chunk_tokens)
            # TF-IDF score
            score = sum(
                (chunk_tokens.count(t) / max(len(chunk_tokens), 1)) * idf[t]
                for t in query_tokens
                if t in chunk_token_set
            )
            if score > 0:
                results.append({
                    "content": chunk.content,
                    "document_id": chunk.document_id,
                    "score": score,
                    "metadata": chunk.metadata,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


# ---------------------------------------------------------------------------
# RAGTool wrapper (for agent tool registry)
# ---------------------------------------------------------------------------

class RAGTool:
    """Thin wrapper exposing RAG as an agent tool."""

    def __init__(self, rag: RAG):
        self.rag = rag

    def query(self, query: str, category: Optional[str] = None) -> str:
        """Query the knowledge base and return formatted context."""
        context = self.rag.get_context(query, max_chars=3000, top_k=6, category=category)
        if not context:
            return "No relevant information found in the knowledge base."
        return context

    def add_document(self, doc_id: str, content: str,
                     metadata: Dict = None) -> str:
        self.rag.add_document(doc_id, content, metadata)
        return f"Document '{doc_id}' added to knowledge base."

    def stats(self) -> str:
        s = self.rag.stats()
        return json.dumps(s, indent=2)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

rag_instance = RAG()
rag_tool = RAGTool(rag_instance)
