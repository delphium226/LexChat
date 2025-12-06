const winston = require('winston');
const DailyRotateFile = require('winston-daily-rotate-file');
const path = require('path');
const fs = require('fs');

// Create logs directory in the server root
const logDir = path.join(__dirname, '../../logs');

if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
}

const logFormat = winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.printf(({ timestamp, level, message, service }) => {
        return `${timestamp} [${service || 'app'}] ${level.toUpperCase()}: ${message}`;
    })
);

// 1. General Application Logs
const appTransport = new DailyRotateFile({
    filename: path.join(logDir, 'app-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    zippedArchive: true,
    maxSize: '20m',
    maxFiles: '14d',
    level: 'info'
});

// 2. Error Logs (Captures errors from all sources)
const errorTransport = new DailyRotateFile({
    filename: path.join(logDir, 'error-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    zippedArchive: true,
    maxSize: '20m',
    maxFiles: '30d',
    level: 'error'
});

// 3. Agent/AI Logs
const agentTransport = new DailyRotateFile({
    filename: path.join(logDir, 'agent-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    zippedArchive: true,
    maxSize: '20m',
    maxFiles: '14d'
});

// 4. HTTP Request Logs
const httpTransport = new DailyRotateFile({
    filename: path.join(logDir, 'http-%DATE%.log'),
    datePattern: 'YYYY-MM-DD',
    zippedArchive: true,
    maxSize: '20m',
    maxFiles: '14d'
});

// Main App Logger
const logger = winston.createLogger({
    defaultMeta: { service: 'app' },
    format: logFormat,
    transports: [
        appTransport,
        errorTransport,
        new winston.transports.Console({
            format: winston.format.combine(
                winston.format.colorize(),
                winston.format.simple()
            )
        })
    ]
});

// Agent Logger
const agentLogger = winston.createLogger({
    defaultMeta: { service: 'agent' },
    format: logFormat,
    transports: [
        agentTransport,
        errorTransport,
        new winston.transports.Console({
            format: winston.format.combine(
                winston.format.colorize(),
                winston.format.simple()
            )
        })
    ]
});

// HTTP Logger
const httpLogger = winston.createLogger({
    defaultMeta: { service: 'http' },
    format: logFormat,
    transports: [
        httpTransport,
        new winston.transports.Console({
            format: winston.format.combine(
                winston.format.colorize(),
                winston.format.simple()
            )
        })
    ]
});

module.exports = {
    logger,
    agentLogger,
    httpLogger
};
