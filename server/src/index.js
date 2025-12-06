const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const { chatWithOllama, listModels } = require('./agent/ollama');
const { logger, httpLogger } = require('./utils/logger');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

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

// Endpoint to list available models
app.get('/api/models', async (req, res) => {
    const models = await listModels();
    res.json(models);
});

// Endpoint for chat
// Endpoint for chat
app.post('/api/chat', async (req, res) => {
    const { messages, model } = req.body;

    if (!messages || !model) {
        return res.status(400).json({ error: 'Missing messages or model' });
    }

    // Set headers for Server-Sent Events
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    try {
        const responseMessage = await chatWithOllama([...messages], model, (status) => {
            if (status.type !== 'token') {
                logger.info(`Tool Status: ${JSON.stringify(status)}`);
            }
            // Stream status updates to client
            res.write(`data: ${JSON.stringify(status)}\n\n`);
        });

        // Send final result
        res.write(`data: ${JSON.stringify({ type: 'result', message: responseMessage })}\n\n`);
        res.end();
    } catch (error) {
        logger.error(`Chat Error: ${error.message}`);
        // Send error event
        res.write(`data: ${JSON.stringify({ type: 'error', error: error.message })}\n\n`);
        res.end();
    }
});

app.listen(PORT, () => {
    logger.info(`Server running on http://localhost:${PORT}`);
});
