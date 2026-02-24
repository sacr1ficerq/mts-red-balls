from kaggle_solver.tools.registry import create_tool
from kaggle_solver.llm import LLM
from kaggle_solver.core.config import ConfigHolder
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


def _translate_query(query: str, llm: LLM) -> str:
    """Translate query to English for better search results."""
    config = ConfigHolder().search_config
    model = config.get("model", "openai/gpt-oss-120b:free")
    prompt = f"""Translate this query to English. Return ONLY the translated query, nothing else.

Query: {query}"""
    try:
        return llm.generate(model=model, prompt=prompt, max_tokens=50).strip()
    except:
        return query


def _evaluate_relevance(query: str, results: List[Dict], llm: LLM) -> List[Dict]:
    """Quickly evaluate relevance of search results using LLM."""
    if not results:
        return []
    
    config = ConfigHolder().search_config
    model = config.get("model", "openai/gpt-oss-120b:free")
    results_subset = results[:5]
    
    results_text = "\n".join([
        f"{i+1}. {r.get('title', 'No title')}: {r.get('body', r.get('href', ''))[:200]}"
        for i, r in enumerate(results_subset)
    ])
    
    prompt = f"""Query: {query}

Search results:
{results_text}

Which results are RELEVANT to the query? List numbers (1-{len(results_subset)}).
Respond ONLY with comma-separated numbers, nothing else. Example: 1,3,4"""

    try:
        response = llm.generate(
            model=model,
            prompt=prompt,
            max_tokens=50
        )
        
        relevant = set()
        for part in response.replace(",", " ").split():
            try:
                relevant.add(int(part.strip()) - 1)
            except ValueError:
                pass
        
        return [results_subset[i] for i in relevant if i < len(results_subset)]
    except Exception as e:
        logger.warning(f"Relevance evaluation failed: {e}")
        return results_subset[:3]


@create_tool(name="search", description="Web search using DuckDuckGo")
def search_tool(query: str, llm=None, sandbox=None) -> str:
    """Real web search using DuckDuckGo with relevance filtering."""
    if llm is None:
        return "Error: LLM not provided"
    
    if not DDGS_AVAILABLE:
        return "Error: duckduckgo-search not installed"
    
    try:
        # Translate query to English for better results
        query_en = _translate_query(query, llm)
        
        # Get raw results from DuckDuckGo (en-US for global results)
        with DDGS() as ddgs:
            results = list(ddgs.text(query_en, max_results=8, region="en-US"))
        
        if not results:
            return f"No results found for: {query}"
        
        # Evaluate relevance and filter
        relevant_results = _evaluate_relevance(query_en, results, llm)
        
        if not relevant_results:
            relevant_results = results[:3]
        
        # Build concise context
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
