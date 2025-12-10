import axios from 'axios';

const API_URL = `http://${window.location.hostname}:3000/api`;

export const getModels = async () => {
    const response = await axios.get(`${API_URL}/models`);
    return response.data;
};

export const sendMessage = (messages, model, num_ctx, onUpdate, signal) => {
    return new Promise(async (resolve, reject) => {
        try {
            const response = await fetch(`${API_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ messages, model, num_ctx }),
                signal
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep the last incomplete chunk

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.type === 'result') {
                                resolve(data.message);
                            } else if (data.type === 'error') {
                                reject(new Error(data.error));
                            } else {
                                if (onUpdate) onUpdate(data);
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            reject(error);
        }
    });
};
