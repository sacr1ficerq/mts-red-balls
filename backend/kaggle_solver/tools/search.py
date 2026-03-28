import asyncio
import logging
import re
from typing import List, Dict

from kaggle_solver.tools.registry import create_tool
from kaggle_solver.llm import LLM
from kaggle_solver.core.config import ConfigHolder

logger = logging.getLogger(__name__)

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


def _translate_query(query: str) -> str:
    """Simple language detection and translation hint."""
    # Check if query contains non-ASCII characters
    if all(ord(c) < 128 for c in query):
        return query
    
    # For non-English queries, add language hint to improve search results
    # This is a simple approach - DuckDuckGo will handle the actual translation
    return query


def _evaluate_relevance_simple(results: List[Dict]) -> List[Dict]:
    """Simple relevance evaluation - just return first results."""
    if not results:
        return []
    # Return top 5 results without LLM-based filtering
    return results[:5]


@create_tool(name="search", description="Web search via DuckDuckGo")
def search_tool(query: str, llm=None, sandbox=None) -> str:
    """Synchronous wrapper for async search."""
    if llm is None:
        return "Error: LLM not provided"
    if not DDGS_AVAILABLE:
        return "Error: duckduckgo-search not installed"
    
    try:
        # Try to get existing event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - use thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _search_impl(query, llm))
                return future.result()
        except RuntimeError:
            # No running loop - use asyncio.run
            return asyncio.run(_search_impl(query, llm))
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Search error: {e}"


async def _search_impl(query: str, llm: LLM) -> str:
    """Async implementation of search."""
    try:
        # Simple translation check (no LLM needed)
        query_en = _translate_query(query)
        if query_en != query:
            logger.info(f"Non-English query detected: {query}")
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=10, safesearch="on"))
        
        if not results:
            return f"No results found for: {query}"
        
        # Simple relevance - just take top results
        relevant_results = _evaluate_relevance_simple(results)
        
        context_parts = [f"Search results for: {query}\n"]
        for i, r in enumerate(relevant_results, 1):
            title = r.get('title', 'No title')
            body = r.get('body', '')
            href = r.get('href', '')
            context_parts.append(f"{i}. {title}")
            if body:
                context_parts.append(f"   {body[:300]}...")
            if href:
                context_parts.append(f"   Source: {href}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Search error: {e}"
