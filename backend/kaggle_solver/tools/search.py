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


def _translate_query(query: str, llm: LLM) -> str:
    if all(ord(c) < 128 for c in query):
        return query
    try:
        prompt = f"Translate to English: {query}"
        result = llm.generate(model="openrouter/free", prompt=prompt, max_tokens=100).strip()
        if result and len(result) > 5:
            return result
    except:
        pass
    return query


def _evaluate_relevance(query: str, results: List[Dict], llm: LLM) -> List[Dict]:
    if not results:
        return []
    
    config = ConfigHolder().search_config
    model = config.get("model", "openrouter/free")
    results_subset = results[:5]
    
    results_text = "\n".join([
        f"{i+1}. {r.get('title', 'No title')}: {r.get('body', r.get('href', ''))[:200]}"
        for i, r in enumerate(results_subset)
    ])
    
    prompt = f"Query: {query}\n\nSearch results:\n{results_text}\n\nWhich results are relevant? List numbers (1-{len(results_subset)})."
    
    try:
        response = llm.generate(model=model, prompt=prompt, max_tokens=50)
        relevant = set()
        numbers = re.findall(r'\d+', response)
        for num in numbers:
            try:
                idx = int(num) - 1
                if 0 <= idx < len(results_subset):
                    relevant.add(idx)
            except ValueError:
                pass
        if not relevant:
            return results_subset[:3]
        return [results_subset[i] for i in sorted(list(relevant))]
    except Exception as e:
        logger.warning(f"Relevance evaluation failed: {e}")
        return results_subset[:3]


@create_tool(name="search", description="Web search via DuckDuckGo")
def search_tool(query: str, llm=None, sandbox=None) -> str:
    if llm is None:
        return "Error: LLM not provided"
    if not DDGS_AVAILABLE:
        return "Error: duckduckgo-search not installed"
    
    try:
        query_en = _translate_query(query, llm)
        logger.info(f"Translated query: {query} -> {query_en}")
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query_en, max_results=10, safesearch="on"))
        
        if not results:
            return f"No results found for: {query}"
        
        relevant_results = _evaluate_relevance(query_en, results, llm)
        if not relevant_results:
            relevant_results = results[:3]
        
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
