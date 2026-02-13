import React, { useState, useEffect, useRef } from 'react';
import { getModels, sendSystemMessage } from '../services/api';

export default function SystemChat() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [models, setModels] = useState([]);
    const [selectedModel, setSelectedModel] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);
    const abortControllerRef = useRef(null);

    useEffect(() => {
        getModels().then((data) => {
            const filteredModels = data.filter(m => m.name.toLowerCase().includes('cloud'));
            setModels(filteredModels);
            if (filteredModels.length > 0) {
                const preferredModel = filteredModels.find(m => m.name === 'mistral-large-3:675b-cloud');
                setSelectedModel(preferredModel ? preferredModel.name : filteredModels[0].name);
            }
        });
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim() || !selectedModel || loading) return;

        const userMsg = { role: 'user', content: input };

        // Setup initial structure for this turn
        const turnId = Date.now();
        setMessages(prev => [...prev, {
            id: turnId,
            type: 'turn',
            user: userMsg,
            events: []
        }]);

        setInput('');
        setLoading(true);

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
            await sendSystemMessage([userMsg], selectedModel, null, (event) => {
                setMessages(prev => {
                    const newMessages = [...prev];
                    const currentTurnIndex = newMessages.findIndex(m => m.id === turnId);

                    if (currentTurnIndex !== -1) {
                        const currentTurn = { ...newMessages[currentTurnIndex] };

                        // For token events, we can aggregate them to reduce noise if desired, 
                        // but user asked for "raw output", so we'll log every event.
                        // Actually, raw token events are too spammy (one per char). 
                        // Let's aggregate tokens into a "partial_response" event but keep others raw.

                        if (event.type === 'token') {
                            const lastEvent = currentTurn.events[currentTurn.events.length - 1];
                            if (lastEvent && lastEvent.type === 'token_stream') {
                                // Update existing token stream
                                lastEvent.content += event.content;
                                // Force update array reference
                                currentTurn.events = [...currentTurn.events];
                            } else {
                                // New token stream
                                currentTurn.events = [...currentTurn.events, { type: 'token_stream', content: event.content }];
                            }
                        } else {
                            currentTurn.events = [...currentTurn.events, event];
                        }

                        newMessages[currentTurnIndex] = currentTurn;
                    }
                    return newMessages;
                });
            }, controller.signal);
        } catch (error) {
            console.error(error);
            setMessages(prev => [...prev, { type: 'error', error: error.message }]);
        } finally {
            setLoading(false);
            abortControllerRef.current = null;
        }
    };

    return (
        <div className="flex flex-col h-screen bg-gray-900 text-green-400 font-mono p-4">
            <header className="mb-4 border-b border-green-700 pb-2 flex justify-between items-center">
                <h1 className="text-xl font-bold">System Chat Terminal</h1>
                <select
                    className="bg-gray-800 border border-green-700 text-green-400 p-1 rounded"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                >
                    {models.map(m => <option key={m.name} value={m.name}>{m.name}</option>)}
                </select>
            </header>

            <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2">
                {messages.map((msg, i) => (
                    <div key={i} className="border border-gray-700 rounded p-2 bg-gray-950/50">
                        {msg.type === 'turn' ? (
                            <>
                                <div className="text-white font-bold mb-2">USER: {msg.user.content}</div>
                                <div className="space-y-1 pl-4 border-l-2 border-gray-800">
                                    {msg.events.map((event, j) => (
                                        <div key={j} className="text-sm break-words">
                                            {event.type === 'token_stream' ? (
                                                <span className="text-gray-300">
                                                    <span className="text-xs text-gray-500 uppercase mr-2">[STREAM]</span>
                                                    {event.content}
                                                </span>
                                            ) : (
                                                <div className="bg-gray-900 p-2 rounded overflow-x-auto">
                                                    <span className={`text-xs uppercase font-bold mr-2 ${getEventColor(event.type)}`}>
                                                        [{event.type}]
                                                    </span>
                                                    <pre className="inline text-xs">{JSON.stringify(omitLargeFields(event), null, 2)}</pre>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="text-red-500">ERROR: {msg.error}</div>
                        )}
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSend} className="flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    className="flex-1 bg-gray-800 border border-gray-700 text-white p-2 rounded focus:outline-none focus:border-green-500"
                    placeholder="Enter system command..."
                    disabled={loading}
                />
                <button
                    type="submit"
                    disabled={loading || !input.trim()}
                    className="bg-green-700 text-white px-6 py-2 rounded hover:bg-green-600 disabled:opacity-50"
                >
                    {loading ? 'EXECUTING...' : 'SEND'}
                </button>
            </form>
        </div>
    );
}

function getEventColor(type) {
    switch (type) {
        case 'tool_call': return 'text-yellow-400';
        case 'tool_result': return 'text-blue-400';
        case 'tool_start': return 'text-cyan-600';
        case 'tool_end': return 'text-cyan-600';
        case 'api_call_start': return 'text-purple-400';
        case 'api_call_end': return 'text-purple-400';
        case 'result': return 'text-green-500';
        case 'error': return 'text-red-500';
        default: return 'text-gray-500';
    }
}

function omitLargeFields(event) {
    // Helper to keep logs readable if result is massive
    if (event.type === 'tool_result' && event.result && event.result.length > 5000) {
        return { ...event, result: event.result.substring(0, 500) + '... [TRUNCATED]' };
    }
    return event;
}
