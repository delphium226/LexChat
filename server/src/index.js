const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');
const config = require('./config');

const app = express();
const PORT = config.server.port || 3000;

app.use(cors());

// HTTP Request Logger (Simplified)
app.use((req, res, next) => {
    console.log(`${new Date().toISOString()} ${req.method} ${req.originalUrl}`);
    next();
});

// Proxy API requests to Python Backend
app.use('/api', createProxyMiddleware({
    target: 'http://backend:8000', // Docker service name for Python backend
    changeOrigin: true,
    ws: true, // Enable Websocket support for streaming if needed
    logLevel: 'debug',
    onError: (err, req, res) => {
        console.error('Proxy Error:', err);
        res.status(500).send('Proxy Error');
    }
}));

// Serve static files from the React client build
app.use(express.static(path.join(__dirname, '../../client/dist')));

// Catch-all handler for SPA (Frontend)
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../../client/dist/index.html'));
});

app.listen(PORT, () => {
    console.log(`Frontend/Proxy Server running on http://localhost:${PORT}`);
    console.log(`Proxying /api requests to http://backend:8000`);
});
