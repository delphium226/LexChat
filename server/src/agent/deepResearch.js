const { chatLoop } = require('./ollama');
const { executeWorkerTool, workerTools } = require('./tools');
const { searchWeb } = require('./webSearch');
const { agentLogger } = require('../utils/logger');
const config = require('../config');

// Define tools available to the Deep Research Agent (Worker + Web)
const deepResearchTools = [
    ...workerTools,
    {
        type: 'function',
        function: {
            name: 'search_web',
            description: 'Search the public web for information. Use this for broad context, news, or general knowledge not in the legal database.',
            parameters: {
                type: 'object',
                properties: {
                    query: {
                        type: 'string',
                        description: 'The search query.',
                    },
                },
                required: ['query'],
            },
        },
    }
];

// Helper to execute tools including web search
async function executeDeepResearchTool(name, args) {
    if (name === 'search_web') {
        const result = await searchWeb(args.query);
        return result;
    }
    return await executeWorkerTool(name, args);
}

const DEEP_RESEARCH_SYSTEM_PROMPT = `You are a Deep Research Agent.
Your goal is to provide a comprehensive, well-researched answer to the user's query.
You have access to:
1. UK Legislation and Case Law Databases (via worker tools).
2. Live Web Search (via search_web).

Follow this iterative process:
1. PLAN: Break down the user's query into search steps.
2. SEARCH: Use web search for context and legal databases for specifics.
3. REFINE: Analyze results. If insufficient, search again (up to 3-5 steps).
4. ANSWER: Synthesize all findings into a detailed final report.
5. CITATIONS: ALWAYS include the source URL for every piece of information using Markdown link format [Title](url). If a URL is not available, mention the source name explicitly.
`;

/**
 * The Deep Research Entry Point
 */
async function chatWithDeepResearch(messages, model, onStatusUpdate, signal, num_ctx) {
    agentLogger.info('[Deep Research] Starting session...');

    // Inject System Prompt
    const systemMessage = {
        role: 'system',
        content: DEEP_RESEARCH_SYSTEM_PROMPT
    };

    let finalMessages = [...messages];
    // Replace or Insert System Prompt
    if (finalMessages.length > 0 && finalMessages[0].role === 'system') {
        finalMessages[0] = systemMessage;
    } else {
        finalMessages = [systemMessage, ...finalMessages];
    }

    // Reuse the generic ChatLoop from ollama.js
    // This handles the ReAct loop automatically (Model -> Tool -> Model -> Tool...)
    // We just provide the expanded toolset and the custom executor.

    return chatLoop(finalMessages, model, signal, num_ctx, deepResearchTools, async (toolName, toolArgs) => {
        // Deep Research Tool Executor
        onStatusUpdate({ type: 'tool_start', tool: `Deep Research: ${toolName}` });

        const result = await executeDeepResearchTool(toolName, toolArgs);

        onStatusUpdate({ type: 'tool_end', tool: `Deep Research: ${toolName}`, result: 'Done' });

        return result;
    }, onStatusUpdate);
}

module.exports = { chatWithDeepResearch };
