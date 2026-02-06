const { v4: uuidv4 } = require('uuid');
const { logger } = require('./logger');

class RequestQueue {
    constructor(concurrency = 5) {
        this.concurrency = concurrency;
        this.active = 0;
        this.queue = [];
    }

    /**
     * Enqueue a task to be executed.
     * @param {Function} taskFactory - A function that returns a Promise.
     * @param {Function} onWaiting - Optional callback (pos) => void, called when task is queued.
     * @returns {Promise<any>}
     */
    enqueue(taskFactory, onWaiting) {
        return new Promise((resolve, reject) => {
            const task = {
                id: uuidv4(),
                factory: taskFactory,
                resolve,
                reject,
                onWaiting
            };

            this.queue.push(task);

            // Notify about position immediately
            if (task.onWaiting) {
                // Position is index + 1
                // But wait, if we process it immediately, it won't be in queue long.
                // We should check if we can run it.
            }

            this.process();
        });
    }

    notifyQueuePositions() {
        this.queue.forEach((task, index) => {
            if (task.onWaiting) {
                task.onWaiting(index + 1);
            }
        });
    }

    async process() {
        if (this.active >= this.concurrency || this.queue.length === 0) {
            // If queued, notify them of their position
            if (this.queue.length > 0) {
                this.notifyQueuePositions();
            }
            return;
        }

        const task = this.queue.shift();
        this.active++;

        // Notify remaining tasks of their new positions
        this.notifyQueuePositions();

        try {
            logger.info(`[Queue] Starting task ${task.id}. Active: ${this.active}`);
            const result = await task.factory();
            task.resolve(result);
        } catch (error) {
            logger.error(`[Queue] Task ${task.id} failed: ${error.message}`);
            task.reject(error);
        } finally {
            this.active--;
            logger.info(`[Queue] Task ${task.id} finished. Active: ${this.active}`);
            this.process();
        }
    }

    getStats() {
        return {
            active: this.active,
            queued: this.queue.length,
            concurrency: this.concurrency
        };
    }
}

// Singleton instance (optional, or can be instantiated in index.js)
module.exports = RequestQueue;
