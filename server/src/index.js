const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const { chatWithOllama, listModels } = require('./agent/ollama');
const { logger, httpLogger } = require('./utils/logger');
const path = require('path');
const config = require('./config');

const app = express();
const PORT = config.server.port;

app.use(cors());
app.use(bodyParser.json());

// HTTP Request Logging Middleware
app.use((req, res, next) => {
    const start = Date.now();
    res.on('finish', () => {
        const duration = Date.now() - start;
        httpLogger.info(`${req.method} ${req.originalUrl} ${res.statusCode} ${duration}ms`);
    });
    next();
});

// Serve static files from the React client build
app.use(express.static(path.join(__dirname, '../../client/dist')));

// Endpoint to list available models
app.get('/api/models', async (req, res) => {
    const models = await listModels();
    res.json(models);
});

// Endpoint for chat
app.post('/api/chat', async (req, res) => {
    const { messages, model, num_ctx } = req.body;

    if (!messages || !model) {
        return res.status(400).json({ error: 'Missing messages or model' });
    }

    // Set headers for Server-Sent Events
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const controller = new AbortController();

    // Abort processing if client disconnects
    res.on('close', () => {
        if (!res.writableEnded) {
            logger.info('Client closed connection early (res.close)');
            controller.abort();
        }
    });

    try {
        const { deep_research } = req.body;

        let responseMessage;
        if (deep_research) {
            const { chatWithDeepResearch } = require('./agent/deepResearch');
            responseMessage = await chatWithDeepResearch([...messages], model, (status) => {
                if (status.type !== 'token') {
                    logger.info(`Tool Status: ${JSON.stringify(status)}`);
                }
                // Stream status updates to client
                if (!controller.signal.aborted) {
                    res.write(`data: ${JSON.stringify(status)}\n\n`);
                }
            }, controller.signal, num_ctx);
        } else {
            responseMessage = await chatWithOllama([...messages], model, (status) => {
                if (status.type !== 'token') {
                    logger.info(`Tool Status: ${JSON.stringify(status)}`);
                }
                // Stream status updates to client
                if (!controller.signal.aborted) {
                    res.write(`data: ${JSON.stringify(status)}\n\n`);
                }
            }, controller.signal, num_ctx);
        }

        // Send final result
        if (!controller.signal.aborted) {
            res.write(`data: ${JSON.stringify({ type: 'result', message: responseMessage })}\n\n`);
            res.end();
        }
    } catch (error) {
        if (error.message === 'Aborted' || error.message === 'canceled' || error.name === 'AbortError' || error.name === 'CanceledError' || error.code === 'ECONNABORTED') {
            logger.info('Client closed connection, aborted processing.');
        } else {
            logger.error(`Chat Error: ${error.message}`);

            let userMessage = error.message;
            // Check for connection refused (Ollama down) or other common connection issues
            if (error.code === 'ECONNREFUSED' || (error.cause && error.cause.code === 'ECONNREFUSED') || error.message.includes('ECONNREFUSED')) {
                userMessage = "Agent Service (Ollama) is not reachable. Please ensure it is running on your machine.";
            }

            // Send error event if channel is still open
            if (!res.writableEnded && !res.finished) {
                res.write(`data: ${JSON.stringify({ type: 'error', error: userMessage })}\n\n`);
            }
        }
        res.end();
    }
});

// Catch-all handler to invoke the React app for any other request (SPA support)
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../../client/dist/index.html'));
});

app.listen(PORT, () => {
    logger.info(`Server running on http://localhost:${PORT}`);
});
