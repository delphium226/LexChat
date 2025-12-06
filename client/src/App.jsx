import React, { useState, useEffect, useRef } from 'react';
import { getModels, sendMessage } from './services/api';
import ChatMessage from './components/ChatMessage';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState('');
  const [contextUsage, setContextUsage] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Fetch models on load
    getModels().then((data) => {
      setModels(data);
      if (data.length > 0) setSelectedModel(data[0].name);
    });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentStatus]); // Scroll on status update too

  const handleSend = async () => {
    if (!input.trim() || !selectedModel) return;

    const userMsg = { role: 'user', content: input };

    // Update UI with User message only (no empty assistant bubble yet)
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setAgentStatus('Thinking...');

    try {
      // Send the message history including the new user message
      // Note: `messages` here refers to the state *before* the current userMsg was added to the UI.
      // The `userMsg` is explicitly added to `messagesToSend`.
      const messagesToSend = [...messages, userMsg];

      const response = await sendMessage(messagesToSend, selectedModel, (status) => {
        if (status.type === 'tool_start') {
          setAgentStatus(`Using tool: ${status.tool}...`);
        } else if (status.type === 'tool_end') {
          setAgentStatus('Processing results...');
        } else if (status.type === 'token') {
          setAgentStatus('Typing...');
          setMessages(prev => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];

            if (lastMsg.role === 'assistant') {
              // Append to existing assistant message
              updated[updated.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + status.content
              };
              return updated;
            } else {
              // Create new assistant message if it doesn't exist yet
              return [...updated, { role: 'assistant', content: status.content }];
            }
          });
        }
      });

      // Final update to ensure consistency
      if (response.stats) {
        setContextUsage(response.stats);
      }

      setMessages(prev => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1];

        if (lastMsg.role === 'assistant') {
          updated[updated.length - 1] = response;
          return updated;
        } else {
          return [...updated, response];
        }
      });

    } catch (error) {
      console.error("Error sending message:", error);
      setMessages(prev => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1];
        const errorMsg = { role: 'assistant', content: "Error: Could not connect to the agent." };

        if (lastMsg.role === 'assistant') {
          updated[updated.length - 1] = errorMsg;
          return updated;
        } else {
          return [...updated, errorMsg];
        }
      });
    } finally {
      setLoading(false);
      setAgentStatus('');
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setInput('');
    setContextUsage(null);
  };

  // Helper to calculate usage percentage
  const getUsagePercentage = () => {
    if (!contextUsage) return 0;
    const total = (contextUsage.prompt_eval_count || 0) + (contextUsage.eval_count || 0);
    return Math.min((total / 131072) * 100, 100);
  };

  return (
    <div className="flex h-screen bg-[#b4b5b8]">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 p-4 flex flex-col">
        <h1 className="text-xl font-bold text-legal-blue mb-6">LexChat</h1>

        <button
          onClick={handleNewChat}
          className="w-full bg-legal-blue text-white p-2 rounded-md mb-6 hover:bg-blue-800 transition-colors font-medium"
        >
          + New Chat
        </button>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Model</label>
          <select
            className="w-full p-2 border rounded-md"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {models.map((m) => (
              <option key={m.name} value={m.name}>{m.name}</option>
            ))}
          </select>
        </div>

        {/* Context Usage Graph */}
        {contextUsage && (
          <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Context Usage</h3>
            <div className="w-full bg-gray-200 rounded-full h-2.5 mb-2">
              <div
                className="bg-legal-blue h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${getUsagePercentage()}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-xs text-gray-600">
              <span>{(contextUsage.prompt_eval_count || 0) + (contextUsage.eval_count || 0)} tokens</span>
              <span>131k limit</span>
            </div>
            <div className="mt-2 text-xs text-gray-400">
              Load: {Math.round(contextUsage.load_duration / 1000000)}ms | Gen: {Math.round(contextUsage.total_duration / 1000000)}ms
            </div>
          </div>
        )}

      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <p className="text-lg">Select a model and start researching.</p>
            </div>
          )}
          {messages.map((msg, idx) => (
            // Filter out tool messages from main view if desired, or let ChatMessage handle them
            (msg.role !== 'tool') && <ChatMessage key={idx} message={msg} />
          ))}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-white p-4 rounded-lg shadow-md">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-legal-blue rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-legal-blue rounded-full animate-bounce delay-75"></div>
                  <div className="w-2 h-2 bg-legal-blue rounded-full animate-bounce delay-150"></div>
                </div>
                <span className="text-xs text-gray-500 mt-1 block">{agentStatus || 'Agent is thinking & researching...'}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-[#8c8e91] border-t border-gray-200">
          <div className="max-w-4xl mx-auto flex space-x-4">
            <input
              type="text"
              className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-legal-blue"
              placeholder="Ask about UK legislation or case law..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              disabled={loading}
            />
            <button
              onClick={handleSend}
              disabled={loading}
              className="bg-legal-blue text-white px-6 py-3 rounded-lg hover:bg-blue-800 disabled:opacity-50 transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
