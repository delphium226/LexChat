const axios = require('axios');
const { tools, executeTool } = require('./tools');
const { agentLogger } = require('../utils/logger');
require('dotenv').config();

const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
const OLLAMA_API_KEY = process.env.OLLAMA_API_KEY;

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
            content: `You are a helpful legal research assistant for UK law.
When you cite legislation or case law, you MUST provide the source URL if available.
- For Legislation: The tools return a 'uri' field (e.g., http://www.legislation.gov.uk/id/...). Use this to create a Markdown link: [Title](uri).
- For Case Law: If a URL is provided, use it. If not, cite the case name and citation clearly.`
        };

        // Only add system message if the first message isn't already a system message
        const finalMessages = messages.length > 0 && messages[0].role === 'system'
            ? messages
            : [systemMessage, ...messages];

        // 1. Initial Call to Ollama
        const payload = {
            model: model,
            messages: finalMessages,
            tools: tools,
            stream: true,
            options: {
                num_ctx: num_ctx || 131072
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
    try {
        const response = await axios.get(`${OLLAMA_BASE_URL}/api/tags`, {
            headers: getHeaders()
        });

        const models = response.data.models;

        // Enhance with details
        const detailedModels = await Promise.all(models.map(async (model) => {
            try {
                const details = await axios.post(`${OLLAMA_BASE_URL}/api/show`, {
                    name: model.name
                }, { headers: getHeaders() });

                let contextLength = null;

                // 1. Try to find context length in model_info (e.g. "llama.context_length", "gemma.context_length")
                if (details.data.model_info) {
                    for (const key in details.data.model_info) {
                        if (key.endsWith('.context_length')) {
                            contextLength = details.data.model_info[key];
                            break;
                        }
                    }
                }

                // 2. If not found, try to parse from parameters (e.g. "num_ctx 4096")
                if (!contextLength && details.data.parameters) {
                    const match = details.data.parameters.match(/num_ctx\s+(\d+)/);
                    if (match) {
                        contextLength = parseInt(match[1]);
                    }
                }

                return { ...model, context_length: contextLength };
            } catch (e) {
                // If detail fetch fails, just return original model
                return model;
            }
        }));

        return detailedModels;
    } catch (error) {
        agentLogger.error(`Failed to list models: ${error.message}`);
        return [];
    }
}

module.exports = { chatWithOllama, listModels };
