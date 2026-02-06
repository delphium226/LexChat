const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const { chatWithOllama, listModels } = require('./agent/ollama');
const { logger, httpLogger } = require('./utils/logger');
const path = require('path');
const config = require('./config');
const cookieParser = require('cookie-parser');
const { initializeDB } = require('./db');
const authRoutes = require('./routes/authRoutes');
const userRoutes = require('./routes/userRoutes');
const RequestQueue = require('./utils/queue');

// Initialize Request Queue
const requestQueue = new RequestQueue(config.concurrency.maxConcurrentRequests);
const { chatWithDeepResearch } = require('./agent/deepResearch'); // Move require up here


const app = express();
const PORT = config.server.port;

app.use(cors());
app.use(bodyParser.json());
app.use(cookieParser());

// Initialize Database
initializeDB();

// Auth Routes
app.use('/api/auth', authRoutes);
app.use('/api/users', userRoutes);
const chatRoutes = require('./routes/chatRoutes');
app.use('/api/chats', chatRoutes);

const learningRoutes = require('./routes/learningRoutes');
app.use('/api/learning', learningRoutes);

const developerRoutes = require('./routes/developerRoutes');
app.use('/api/developer', developerRoutes);

const statsRoutes = require('./routes/statsRoutes');
app.use('/api/stats', statsRoutes);

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

        // Wrap AI execution in the Queue
        const responseMessage = await requestQueue.enqueue(async () => {
            // Timeout to notify user of long processing
            const PROCESS_TIMEOUT_MS = 120000; // 2 minutes
            let timeoutId = setTimeout(() => {
                logger.info('Process timeout triggered - sending warning to client');
                if (!controller.signal.aborted) {
                    res.write(`data: ${JSON.stringify({ type: 'warning', message: 'The request is taking longer than usual. Please be patient, it is being worked on...' })}\n\n`);
                } else {
                    logger.info('Process timeout triggered but signal aborted');
                }
            }, PROCESS_TIMEOUT_MS);

            try {
                if (deep_research) {
                    return await chatWithDeepResearch([...messages], model, (status) => {
                        if (status.type !== 'token') {
                            logger.info(`Tool Status: ${JSON.stringify(status)}`);
                        }
                        // Stream status updates to client
                        if (!controller.signal.aborted) {
                            res.write(`data: ${JSON.stringify(status)}\n\n`);
                        }
                    }, controller.signal, num_ctx);
                } else {
                    return await chatWithOllama([...messages], model, (status) => {
                        if (status.type !== 'token') {
                            logger.info(`Tool Status: ${JSON.stringify(status)}`);
                        }
                        // Stream status updates to client
                        if (!controller.signal.aborted) {
                            res.write(`data: ${JSON.stringify(status)}\n\n`);
                        }
                    }, controller.signal, num_ctx);
                }
            } finally {
                clearTimeout(timeoutId);
            }
        }, (position) => {
            // onWaiting callback: Notify user of their position
            if (!controller.signal.aborted) {
                res.write(`data: ${JSON.stringify({ type: 'queue', message: `Your request has been queued. Current position is #${position}` })}\n\n`);
            }
        });

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
