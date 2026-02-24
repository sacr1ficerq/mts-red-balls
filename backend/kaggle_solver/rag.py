from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
import re
import json

from kaggle_solver.core.config import ConfigHolder

logger = logging.getLogger(__name__)


class Document:
    def __init__(self, content: str, metadata: Dict[str, Any] = None):
        self.content = content
        self.metadata = metadata or {}


class Chunk:
    def __init__(self, content: str, document_id: str, metadata: Dict[str, Any] = None):
        self.content = content
        self.document_id = document_id
        self.metadata = metadata or {}


class RAG:
    def __init__(self, chunk_size: int = 500, overlap: int = 50, llm=None):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.llm = llm
        self.documents: Dict[str, Document] = {}
        self.chunks: List[Chunk] = []

    def add_document(self, doc_id: str, content: str, metadata: Dict = None):
        self.documents[doc_id] = Document(content, metadata)
        doc_chunks = self._chunk_text(content, doc_id, metadata)
        self.chunks.extend(doc_chunks)
        logger.info(f"Added document {doc_id} with {len(doc_chunks)} chunks")

    def _chunk_text(self, text: str, doc_id: str, metadata: Dict = None) -> List[Chunk]:
        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += " " + sentence
            else:
                if current_chunk:
                    chunks.append(Chunk(current_chunk.strip(), doc_id, metadata))
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(Chunk(current_chunk.strip(), doc_id, metadata))
        
        return chunks

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results = []
        for chunk in self.chunks:
            chunk_words = set(chunk.content.lower().split())
            overlap = len(query_words & chunk_words)
            
            if overlap > 0:
                results.append({
                    "content": chunk.content,
                    "document_id": chunk.document_id,
                    "score": overlap,
                    "metadata": chunk.metadata
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def answer(self, query: str, context: str = None) -> str:
        relevant_chunks = self.search(query, top_k=3)
        
        if not relevant_chunks:
            return "No relevant information found."
        
        context_text = "\n\n".join([c["content"] for c in relevant_chunks])
        
        if self.llm is None:
            return f"Context: {context_text}\n\nQuestion: {query}"
        
        config = ConfigHolder().search_config
        model = config.get("model", "openai/gpt-oss-120b:free")
        
        prompt = f"""Based on the following context, answer the question.

Context:
{context_text}

Question: {query}

Answer:"""
        
        try:
            return self.llm.generate(
                model=model,
                prompt=prompt,
                max_tokens=500
            )
        except Exception as e:
            logger.error(f"RAG answer error: {e}")
            return f"Error generating answer: {e}"

    def get_context(self, query: str, max_chars: int = 2000) -> str:
        relevant_chunks = self.search(query, top_k=10)
        
        context = ""
        for chunk in relevant_chunks:
            if len(context) + len(chunk["content"]) > max_chars:
                break
            context += chunk["content"] + "\n\n"
        
        return context.strip()

    def load_documents_from_directory(self, directory: Path, file_patterns: List[str] = None):
        if file_patterns is None:
            file_patterns = ["*.txt", "*.md", "*.py", "*.json"]
        
        for pattern in file_patterns:
            for file_path in directory.rglob(pattern):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    doc_id = str(file_path.relative_to(directory))
                    self.add_document(doc_id, content, {"source": str(file_path)})
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")

    def clear(self):
        self.documents.clear()
        self.chunks.clear()


class RAGTool:
    def __init__(self, rag: RAG):
        self.rag = rag

    def query(self, query: str) -> str:
        context = self.rag.get_context(query)
        return context

    def add_document(self, doc_id: str, content: str) -> str:
        self.rag.add_document(doc_id, content)
        return f"Document {doc_id} added"


rag_instance = RAG()
rag_tool = RAGTool(rag_instance)
