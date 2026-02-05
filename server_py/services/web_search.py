from duckduckgo_search import DDGS
import logging

logger = logging.getLogger("lexchat.web_search")

async def search_web(query: str) -> str:
    logger.info(f"[Web Search] Searching for: {query}")
    try:
        results = DDGS().text(query, max_results=5)
        
        if not results:
            logger.warning(f"[Web Search] No results returned for query: {query}")
            return "No web results found."
            
        formatted = ""
        for i, r in enumerate(results):
            title = r.get('title', 'No Title')
            link = r.get('href', 'No Link')
            snippet = r.get('body', 'No snippet available.')
            formatted += f"[Result {i + 1}]\nTitle: {title}\nSource: {link}\nSnippet: {snippet}\n\n"
            
        return formatted
        
    except Exception as e:
        logger.error(f"[Web Search] Error: {e}")
        return f"Error performing web search: {e}"
