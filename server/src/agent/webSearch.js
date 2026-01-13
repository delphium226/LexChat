const { search } = require('google-sr');
const { agentLogger } = require('../utils/logger');

/**
 * Performs a web search using Google (via google-sr scraper).
 * @param {string} query - The search query.
 * @returns {Promise<string>} - formatted search results.
 */
async function searchWeb(query) {
    agentLogger.info(`[Web Search] Searching for: ${query}`);
    try {
        // google-sr expects an object with a query property
        const results = await search({ query });

        if (!results || results.length === 0) {
            agentLogger.warn(`[Web Search] No results returned for query: ${query}`);
            return "No web results found.";
        }

        // Filter and format results
        // google-sr returns mixed types (OrganicResult, TranslateResult, etc.)
        // We iterate and extract what we can.
        const formatted = results.slice(0, 5).map((r, i) => {
            // Common properties might differ, try to find title/link/desc
            const title = r.title || 'No Title';
            const link = r.link || r.url || 'No Link';
            const snippet = r.description || r.snippet || 'No snippet available.';
            return `[Result ${i + 1}]\nTitle: ${title}\nSource: ${link}\nSnippet: ${snippet}\n`;
        }).join('\n');

        return formatted;
    } catch (error) {
        agentLogger.error(`[Web Search] Error: ${error.message}`);
        return `Error performing web search: ${error.message}`;
    }
}

module.exports = { searchWeb };
