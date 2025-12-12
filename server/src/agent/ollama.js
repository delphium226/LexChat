const axios = require('axios');
const { tools, executeTool } = require('./tools');
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

async function chatWithOllama(messages, model, onChunk, signal, num_ctx) {
    try {
        if (signal && signal.aborted) {
            throw new Error('Aborted');
        }

        // 0. Prepend System Prompt if not present
        const systemMessage = {
            role: 'system',
            content: config.ollama.systemMessage
        };

        // Only add system message if the first message isn't already a system message
        const finalMessages = messages.length > 0 && messages[0].role === 'system'
            ? messages
            : [systemMessage, ...messages];

        // 1. Initial Call to Ollama
        const configuredModel = config.models.find(m => m.name === model);
        const defaultModelContext = configuredModel ? (configuredModel.contextLengthKB * 1024) : config.ollama.defaultContext;

        const payload = {
            model: model,
            messages: finalMessages,
            tools: tools,
            stream: true,
            options: {
                num_ctx: num_ctx || defaultModelContext
            }
        };

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
                response.data.destroy(); // Stop reading stream
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
                            onChunk({ type: 'content', content: content });
                        }

                        if (json.message.tool_calls) {
                            json.message.tool_calls.forEach(tc => {
                                toolCalls.push(tc);
                            });
                        }
                    }
                } catch (e) {
                    // ignore
                }
            }
        }

        const message = {
            role: 'assistant',
            content: fullContent,
        };

        if (stats) {
            message.stats = stats;
        }

        if (toolCalls.length > 0) {
            message.tool_calls = toolCalls;
        }

        if (message.tool_calls && message.tool_calls.length > 0) {
            agentLogger.info(`Tool calls requested: ${message.tool_calls.length}`);

            const nextMessages = [...finalMessages, message];

            // Execute each tool
            for (const toolCall of message.tool_calls) {
                if (signal && signal.aborted) throw new Error('Aborted');

                const functionName = toolCall.function.name;
                const args = toolCall.function.arguments;

                if (onChunk) onChunk({ type: 'tool_start', tool: functionName });

                const toolResult = await executeTool(functionName, args);

                // Add result to history
                nextMessages.push({
                    role: 'tool',
                    content: toolResult,
                    name: functionName,
                });

                if (onChunk) onChunk({ type: 'tool_end', tool: functionName, result: 'Done' });
            }

            // 3. Follow-up Call to Ollama (Recursion)
            return chatWithOllama(nextMessages, model, onChunk, signal, num_ctx);
        }

        // No tool calls, just return the text response
        return message;

    } catch (error) {
        if (error.message === 'Aborted' || axios.isCancel(error)) {
            agentLogger.info('Ollama request aborted');
            throw error;
        }
        agentLogger.error(`Ollama Error: ${error.message}`);
        throw error;
    }
}

async function listModels() {
    return config.models.map(model => ({
        name: model.name,
        context_length: model.contextLengthKB * 1024
    }));
}

module.exports = { chatWithOllama, listModels };
