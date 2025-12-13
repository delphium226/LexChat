const axios = require('axios');
const { managerTools, workerTools, executeWorkerTool } = require('./tools');
const { agentLogger } = require('../utils/logger');
const config = require('../config');

const OLLAMA_BASE_URL = config.ollama.baseUrl;
const OLLAMA_API_KEY = config.ollama.apiKey;

const getHeaders = () => {
    const headers = {};
    if (OLLAMA_API_KEY) {
        headers['Authorization'] = `Bearer ${OLLAMA_API_KEY}`;
    }
    return headers;
};

// ----------------------------------------------------------------------
// WORKER LOOP (Research Agent)
// ----------------------------------------------------------------------

async function runWorkerAgent(query, model, signal, num_ctx, parentOnChunk) {
    agentLogger.info(`[Worker] Starting research on: ${query}`);

    // Worker starts with a fresh context
    const messages = [
        { role: 'system', content: config.ollama.systemMessage.worker },
        { role: 'user', content: query }
    ];

    // Pass null for onChunk to suppress worker token streaming
    return chatLoop(messages, model, signal, num_ctx, workerTools, async (toolName, toolArgs) => {
        // executeWorkerTool wrapper
        if (parentOnChunk) parentOnChunk({ type: 'tool_start', tool: `Worker: ${toolName}` });
        const result = await executeWorkerTool(toolName, toolArgs);
        if (parentOnChunk) parentOnChunk({ type: 'tool_end', tool: `Worker: ${toolName}`, result: 'Done' });
        return result;
    }, null);
}


// ----------------------------------------------------------------------
// MANAGER LOOP (Chat Interface)
// ----------------------------------------------------------------------

async function processUserRequest(messages, model, onChunk, signal, num_ctx) {
    // Ensure system prompt is set for Manager
    const systemMessage = {
        role: 'system',
        content: config.ollama.systemMessage.manager
    };

    let finalMessages = [...messages];
    if (finalMessages.length === 0 || finalMessages[0].role !== 'system') {
        finalMessages = [systemMessage, ...finalMessages];
    }

    // Pass onChunk to allow Manager to stream tokens
    return chatLoop(finalMessages, model, signal, num_ctx, managerTools, async (toolName, toolArgs) => {
        // Manager Tools Execution
        if (toolName === 'delegate_research') {
            if (onChunk) onChunk({ type: 'tool_start', tool: 'Research Agent' });

            // Call the Worker!
            const researchResult = await runWorkerAgent(toolArgs.query, model, signal, num_ctx, onChunk);

            if (onChunk) onChunk({ type: 'tool_end', tool: 'Research Agent', result: 'Research Complete' });

            return `[Research Agent Result]\n${researchResult.content}`;
        }
        return `Error: Unknown manager tool ${toolName}`;
    }, onChunk);
}


// ----------------------------------------------------------------------
// GENERIC CHAT LOOP (Used by both Manager and Worker)
// ----------------------------------------------------------------------

async function chatLoop(messages, model, signal, num_ctx, tools, toolExecutor, onChunk) {
    try {
        if (signal && signal.aborted) throw new Error('Aborted');

        // Prepare Payload
        const configuredModel = config.models.find(m => m.name === model);
        const defaultModelContext = configuredModel ? (configuredModel.contextLengthKB * 1024) : config.ollama.defaultContext;

        const payload = {
            model: model,
            messages: messages,
            tools: tools,
            stream: true,
            options: { num_ctx: num_ctx || defaultModelContext }
        };

        agentLogger.info(`[ChatLoop] Sending request to Ollama (Tools: ${tools.length})...`);

        const response = await axios.post(`${OLLAMA_BASE_URL}/api/chat`, payload, {
            responseType: 'stream',
            headers: getHeaders(),
            signal: signal
        });

        let fullContent = '';
        let toolCalls = [];
        let stats = null;

        for await (const chunk of response.data) {
            if (signal && signal.aborted) {
                response.data.destroy();
                throw new Error('Aborted');
            }

            const lines = chunk.toString().split('\n').filter(line => line.trim() !== '');
            for (const line of lines) {
                try {
                    const json = JSON.parse(line);

                    if (json.done) {
                        stats = {
                            total_duration: json.total_duration,
                            load_duration: json.load_duration,
                            prompt_eval_count: json.prompt_eval_count,
                            eval_count: json.eval_count
                        };
                    }

                    if (json.message) {
                        const content = json.message.content || '';
                        fullContent += content;

                        if (content && onChunk) {
                            onChunk({ type: 'token', content: content });
                        }

                        if (json.message.tool_calls) {
                            json.message.tool_calls.forEach(tc => toolCalls.push(tc));
                        }
                    }
                } catch (e) { /* ignore */ }
            }
        }

        const message = { role: 'assistant', content: fullContent };
        if (stats) message.stats = stats;
        if (toolCalls.length > 0) message.tool_calls = toolCalls;

        if (message.tool_calls && message.tool_calls.length > 0) {
            agentLogger.info(`Tool calls: ${message.tool_calls.length}`);
            const nextMessages = [...messages, message];

            for (const toolCall of message.tool_calls) {
                if (signal && signal.aborted) throw new Error('Aborted');
                const functionName = toolCall.function.name;
                const args = toolCall.function.arguments;

                // Execute via the provided executor (Manager or Worker logic)
                const toolResult = await toolExecutor(functionName, args);

                nextMessages.push({
                    role: 'tool',
                    content: toolResult,
                    name: functionName,
                });
            }
            // Recursion
            return chatLoop(nextMessages, model, signal, num_ctx, tools, toolExecutor, onChunk);
        }

        return message;

    } catch (e) {
        agentLogger.error(`ChatLoop Error Stack: ${e.stack}`);
        throw e;
    }
}

async function listModels() {
    return config.models.map(model => ({
        name: model.name,
        context_length: model.contextLengthKB * 1024
    }));
}

module.exports = {
    chatWithOllama: processUserRequest,
    listModels
};
