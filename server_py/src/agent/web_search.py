import logging

import httpx

logger = logging.getLogger("agent")


async def search_web(query: str) -> str:
    """Perform a web search and return formatted results.

    Uses a lightweight Google scraping approach via httpx.
    Falls back gracefully if search fails.
    """
    logger.info(f"[Web Search] Searching for: {query}")

    try:
        # Use Google's public search and parse results
        # This is a lightweight alternative to google-sr (Node.js)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.google.com/search",
                params={"q": query, "num": 5},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
                follow_redirects=True,
            )
            resp.raise_for_status()

            # Basic extraction from HTML
            from html.parser import HTMLParser

            class GoogleResultParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self._in_h3 = False
                    self._current_title = ""
                    self._current_link = ""

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "a" and attrs_dict.get("href", "").startswith("/url?q="):
                        raw = attrs_dict["href"]
                        url = raw.split("/url?q=")[1].split("&")[0]
                        self._current_link = url
                    if tag == "h3":
                        self._in_h3 = True
                        self._current_title = ""

                def handle_endtag(self, tag):
                    if tag == "h3" and self._in_h3:
                        self._in_h3 = False
                        if self._current_title and self._current_link:
                            self.results.append(
                                {
                                    "title": self._current_title,
                                    "link": self._current_link,
                                }
                            )
                            self._current_link = ""

                def handle_data(self, data):
                    if self._in_h3:
                        self._current_title += data

            parser = GoogleResultParser()
            parser.feed(resp.text)

            if not parser.results:
                logger.warning(f"[Web Search] No results parsed for query: {query}")
                return "No web results found."

            formatted = []
            for i, r in enumerate(parser.results[:5]):
                formatted.append(
                    f"[Result {i + 1}]\n"
                    f"Title: {r['title']}\n"
                    f"Source: {r['link']}\n"
                )

            return "\n".join(formatted)

    except Exception as e:
        logger.error(f"[Web Search] Error: {e}")
        return f"Error performing web search: {str(e)}"
