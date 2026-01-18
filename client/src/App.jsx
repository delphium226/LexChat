import React, { useState, useEffect, useRef } from 'react';
import { getModels, sendMessage } from './services/api';
import ChatMessage from './components/ChatMessage';
import loadingGif from './assets/load-35_128.gif';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginModal from './components/LoginModal';
import AdminPortal from './pages/AdminPortal';
import Settings from './pages/Settings';

function AppContent() {
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState('');
  const [contextUsage, setContextUsage] = useState(null);
  const [showAbout, setShowAbout] = useState(false);
  const [showThinking, setShowThinking] = useState(false);
  const [deepResearchEnabled, setDeepResearchEnabled] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 768; // 768px is tailwind 'md' breakpoint
    }
    return false;
  });

  const [currentView, setCurrentView] = useState('chat'); // 'chat', 'admin', 'settings'

  // Modals State
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showAdminModal, setShowAdminModal] = useState(false);

  // Dark Mode State
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('darkMode');
      if (saved !== null) {
        return saved === 'true';
      }
      return false; // Default to light mode
    }
    return false;
  });

  const [showSettings, setShowSettings] = useState(false);
  const [showSettingsMenu, setShowSettingsMenu] = useState(false);
  const settingsMenuRef = useRef(null);

  // Close server menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (settingsMenuRef.current && !settingsMenuRef.current.contains(event.target)) {
        setShowSettingsMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Apply Dark Mode effect
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode]);
  const messagesEndRef = useRef(null);

  const abortControllerRef = useRef(null);

  const sendingRef = useRef(false);

  useEffect(() => {
    // Fetch models on load
    getModels().then((data) => {
      const filteredModels = data.filter(m => m.name.toLowerCase().includes('cloud'));
      setModels(filteredModels);
      if (filteredModels.length > 0) {
        const preferredModel = filteredModels.find(m => m.name === 'gpt-oss:120b-cloud');
        setSelectedModel(preferredModel ? preferredModel.name : filteredModels[0].name);
      }
    });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentStatus]); // Scroll on status update too

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setLoading(false);
      sendingRef.current = false;
      setAgentStatus('Stopped by user.');
    }
  };

  const handleSend = async (manualContent = null) => {
    if (sendingRef.current) return;

    const contentToSend = typeof manualContent === 'string' ? manualContent : input;
    if (!contentToSend.trim() || !selectedModel) return;

    sendingRef.current = true;

    // Abort previous request if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const userMsg = { role: 'user', content: contentToSend };

    // Update UI with User message only (no empty assistant bubble yet)
    setMessages(prev => [...prev, userMsg]);

    if (typeof manualContent !== 'string') {
      setInput('');
    }

    setLoading(true);
    setAgentStatus('Thinking...');

    try {
      // Send the message history including the new user message
      // Note: `messages` here refers to the state *before* the current userMsg was added to the UI.
      // The `userMsg` is explicitly added to `messagesToSend`.
      const messagesToSend = [...messages, userMsg];

      const currentModelObj = models.find(m => m.name === selectedModel);
      const contextLength = currentModelObj ? currentModelObj.context_length : null;

      const response = await sendMessage(messagesToSend, selectedModel, contextLength, (status) => {
        if (status.type === 'tool_start') {
          const toolMessages = {
            'Research Agent': 'Delegating to research agent...',
            'Worker: search_legislation': 'Querying National Legislation Archives...',
            'Worker: get_legislation_text': 'Reviewing statutory text in detail...',
            'Worker: search_caselaw': 'Analyzing Case Law precedents...',
            'search_legislation': 'Querying National Legislation Archives...',
            'get_legislation_text': 'Reviewing statutory text in detail...',
            'search_caselaw': 'Analyzing Case Law precedents...'
          };
          setAgentStatus(toolMessages[status.tool] || `Conducting research (${status.tool})...`);
        } else if (status.type === 'tool_end') {
          setAgentStatus('Analyzing findings...');
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
      }, controller.signal, deepResearchEnabled);

      // Final update to ensure consistency
      if (response.stats) {
        setContextUsage(prev => {
          const prevTotal = prev ? (prev.total_usage || (prev.prompt_eval_count + prev.eval_count)) : 0;
          const currentTotal = response.stats.prompt_eval_count + response.stats.eval_count;

          let validTotal = currentTotal;
          // If the reported total is significantly less than previous, it's likely a cache hit delta.
          // We accumulate to approximate the true context.
          if (currentTotal < prevTotal) {
            validTotal = prevTotal + currentTotal;
          }

          return { ...response.stats, total_usage: validTotal }; // Store our calculated total
        });
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
      if (error.name === 'AbortError' || error.message.includes('aborted') || error.message.includes('canceled')) {
        console.log('Request aborted/canceled');
        // Optional: Add a message indicating it was stopped?
        // setMessages(prev => [...prev, { role: 'assistant', content: "🛑 [Stopped]" }]);
      } else {
        console.error("Error sending message:", error);

        const getUserFriendlyError = (err) => {
          const match = err.message.match(/status code (\d{3})/);
          if (match) {
            const code = parseInt(match[1]);
            const statusText = {
              400: 'Bad Request',
              401: 'Unauthorized',
              403: 'Forbidden',
              404: 'Not Found',
              408: 'Request Timeout',
              429: 'Too Many Requests',
              500: 'Internal Server Error',
              502: 'Bad Gateway',
              503: 'Service Unavailable',
              504: 'Gateway Timeout'
            }[code] || 'Unknown Error';

            return `Error: ${statusText} (${code})`;
          }
          return `Error: ${err.message}`;
        };

        const formattedErrorMsg = getUserFriendlyError(error);

        setMessages(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          const errorMsg = { role: 'assistant', content: formattedErrorMsg };

          if (lastMsg.role === 'assistant') {
            updated[updated.length - 1] = errorMsg;
            return updated;
          } else {
            return [...updated, errorMsg];
          }
        });
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
        setAgentStatus('');
        abortControllerRef.current = null;
        sendingRef.current = false;
      }
    }
  };

  const handleNewChat = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setMessages([]);
    setInput('');
    setContextUsage(null);
  };

  // Helper to calculate usage percentage
  const getUsagePercentage = () => {
    const currentModelObj = models.find(m => m.name === selectedModel);
    const maxContext = currentModelObj?.context_length || 131072;
    // Use our calculated total_usage if available
    const total = contextUsage ? (contextUsage.total_usage || ((contextUsage.prompt_eval_count || 0) + (contextUsage.eval_count || 0))) : 0;
    return Math.min((total / maxContext) * 100, 100);
  };

  const formatContextLength = (length) => {
    if (!length) return 'Unknown';
    if (length >= 1024) {
      return (length / 1024) + 'k';
    }
    return length;
  };

  if (!user) {
    return <LoginModal />;
  }

  return (
    <div className="flex h-dvh bg-[#b4b5b8] dark:bg-gray-900 overflow-hidden transition-colors duration-200">
      {/* Mobile Backdrop */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden transition-opacity"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col transition-all duration-300 
          fixed md:relative inset-y-0 left-0 z-30 h-full
          ${isSidebarOpen
            ? 'translate-x-0 w-64 p-4'
            : '-translate-x-full md:translate-x-0 md:w-0 md:p-0 md:overflow-hidden w-64'
          }
        `}
      >
        <h1 className="text-3xl font-bold text-blue-600 mb-2 self-center">LexChat</h1>
        <div className="mb-4 text-center text-sm text-gray-500 text-ellipsis overflow-hidden">
          Welcome, {user.username}
        </div>

        <button
          onClick={() => { handleNewChat(); }}
          className="w-full text-center p-2 rounded-md mb-2 hover:bg-blue-700 transition-colors font-medium bg-blue-600 text-white text-lg"
        >
          New chat
        </button>




        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Model</label>
          <select
            className="w-full p-2 border rounded-md disabled:bg-gray-100 disabled:text-gray-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white dark:disabled:bg-gray-800 dark:disabled:text-gray-600"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={messages.length > 0}
          >
            {models.map((m) => (
              <option key={m.name} value={m.name}>{m.name}</option>
            ))}
          </select>
        </div>

        {/* Deep Research Toggle */}
        <div className="mb-6">
          <label className="flex items-center cursor-pointer">
            <div className="relative">
              <input
                type="checkbox"
                className="sr-only"
                checked={deepResearchEnabled}
                onChange={() => setDeepResearchEnabled(!deepResearchEnabled)}
                disabled={messages.length > 0}
              />
              <div className={`block w-10 h-6 rounded-full transition-colors ${deepResearchEnabled ? 'bg-legal-blue' : 'bg-gray-300'}`}></div>
              <div className={`dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform ${deepResearchEnabled ? 'transform translate-x-4' : ''}`}></div>
            </div>
            <div className="ml-3 text-sm font-medium text-gray-700 dark:text-gray-300">
              Deep Research
            </div>
          </label>
        </div>

        {/* Context Usage Graph */}
        {
          selectedModel && (
            <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Chat Memory</h3>
              <div className="w-full bg-gray-200 rounded-full h-2.5 mb-2">
                <div
                  className={`h-2.5 rounded-full transition-all duration-500 ${getUsagePercentage() >= 90 ? 'bg-red-500' :
                    getUsagePercentage() >= 75 ? 'bg-orange-500' : 'bg-legal-blue'
                    }`}
                  style={{
                    width: `${getUsagePercentage()}%`
                  }}
                ></div>
              </div>
              <div className="flex justify-between text-xs text-gray-600">
                <span>{contextUsage ? (contextUsage.total_usage || ((contextUsage.prompt_eval_count || 0) + (contextUsage.eval_count || 0))) : 0} tokens</span>
                <span>{(() => {
                  const currentModelObj = models.find(m => m.name === selectedModel);
                  const maxContext = currentModelObj?.context_length || 131072;
                  return formatContextLength(maxContext);
                })()} limit</span>
              </div>
              {contextUsage && (
                <div className="mt-2 text-xs text-gray-400">
                  Load: {(contextUsage.load_duration / 1000000000).toFixed(2)}s | Gen: {(contextUsage.total_duration / 1000000000).toFixed(2)}s
                </div>
              )}
            </div>
          )
        }


        {/* Global Sidebar Footer Items */}
        <div className="mt-auto relative" ref={settingsMenuRef}>
          {showSettingsMenu && (
            <div className="absolute bottom-full left-0 mb-2 w-60 bg-gray-50 dark:bg-gray-700 rounded-lg shadow-2xl border border-gray-300 dark:border-gray-600 overflow-hidden z-50">
              {/* Account Settings */}
              <button
                onClick={() => { setShowSettingsModal(true); setShowSettingsMenu(false); }}
                className="w-full text-left px-4 py-3 hover:bg-blue-50 dark:hover:bg-gray-700 text-sm text-gray-700 dark:text-gray-200"
              >
                ⚙️ Account Settings
              </button>

              {/* Admin Portal (Conditional) */}
              {user.role === 'admin' && (
                <button
                  onClick={() => { setShowAdminModal(true); setShowSettingsMenu(false); }}
                  className="w-full text-left px-4 py-3 hover:bg-blue-50 dark:hover:bg-gray-700 text-sm text-gray-700 dark:text-gray-200"
                >
                  👥 Admin Portal
                </button>
              )}

              <div className="border-t border-gray-100 dark:border-gray-700 my-1"></div>

              {/* Dark Mode Toggle */}
              <div className="flex items-center justify-between px-4 py-3 hover:bg-blue-50 dark:hover:bg-gray-700 cursor-pointer" onClick={() => setDarkMode(!darkMode)}>
                <span className="text-sm text-gray-700 dark:text-gray-200">Dark Mode</span>
                <div
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${darkMode ? 'bg-legal-blue' : 'bg-gray-400'}`}
                >
                  <span
                    className={`${darkMode ? 'translate-x-5' : 'translate-x-1'} inline-block h-3 w-3 transform rounded-full bg-white transition-transform`}
                  />
                </div>
              </div>

              {/* About */}
              <button
                onClick={() => { setShowAbout(true); setShowSettingsMenu(false); }}
                className="w-full text-left px-4 py-3 hover:bg-blue-50 dark:hover:bg-gray-700 text-sm text-gray-700 dark:text-gray-200"
              >
                ℹ️ About LexChat
              </button>

              <div className="border-t border-gray-100 dark:border-gray-700 my-1"></div>

              {/* Logout */}
              <button
                onClick={logout}
                className="w-full text-left px-4 py-3 hover:bg-red-50 dark:hover:bg-red-900/20 text-sm text-red-600 dark:text-red-400"
              >
                🚪 Log Out
              </button>
            </div>
          )}

          <button
            onClick={() => setShowSettingsMenu(!showSettingsMenu)}
            className={`flex items-center w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors font-medium ${showSettingsMenu ? 'bg-gray-100 dark:bg-gray-700 text-legal-blue' : 'text-gray-700 dark:text-gray-300'}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6 mr-3">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Settings
          </button>
        </div>

      </div >

      {/* Main Content Area */}
      < div className="flex-1 flex flex-col relative w-full overflow-hidden" >
        {/* Sidebar Toggle Button */}
        < button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)
          }
          className="absolute top-4 left-4 z-10 p-2 bg-gray-200 dark:bg-gray-700 dark:text-white rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 transition-all duration-300 shadow-sm"
          title={isSidebarOpen ? "Collapse Sidebar" : "Expand Sidebar"}
        >
          {
            isSidebarOpen ? (
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5" >
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 4.5l7.5 7.5-7.5 7.5m-6-15l7.5 7.5-7.5 7.5" />
              </svg>
            )}
        </button >


        {/* VIEWS */}

        <div className="flex-1 overflow-y-auto p-6 pt-16">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
              <p className="text-lg">Select a model and start researching.</p>
            </div>
          )}
          {messages.map((msg, idx) => (
            // Filter out tool messages from main view if desired, or let ChatMessage handle them
            (msg.role !== 'tool') && <ChatMessage key={idx} message={msg} onResend={() => handleSend(msg.content)} showThinking={showThinking} />
          ))}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-black dark:bg-gray-800 border border-legal-blue p-3 rounded-lg shadow-md flex items-center gap-2 max-w-[85%]">
                <img src={loadingGif} alt="Processing..." className="w-6 h-6 flex-shrink-0" />
                <span className="text-xs text-white dark:text-gray-200 truncate">{agentStatus || 'Agent is thinking...'}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-[#8c8e91] dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 z-40 relative">
          <form
            className="max-w-4xl mx-auto flex space-x-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!loading) handleSend();
            }}
          >
            <input
              type="text"
              className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-legal-blue dark:bg-gray-700 dark:border-gray-600 dark:text-white dark:placeholder-gray-400"
              placeholder="Ask about UK legislation or case law..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            {loading ? (
              <button
                type="button"
                onClick={handleStop}
                className="bg-red-500 text-white px-6 py-3 rounded-lg hover:bg-red-600 transition-colors flex items-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 7.5A2.25 2.25 0 017.5 5.25h9a2.25 2.25 0 012.25 2.25v9a2.25 2.25 0 01-2.25 2.25h-9a2.25 2.25 0 01-2.25-2.25v-9z" />
                </svg>
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="bg-legal-blue text-white px-6 py-3 rounded-lg hover:bg-blue-800 disabled:opacity-50 transition-colors"
              >
                Send
              </button>
            )}
          </form>
        </div>


      </div >
      {/* About Modal */}
      {
        showAbout && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full shadow-xl">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-legal-blue dark:text-legal-gold">About LexChat</h2>
                <button
                  onClick={() => setShowAbout(false)}
                  className="text-gray-400 hover:text-gray-600 focus:outline-none"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4 text-gray-700 dark:text-gray-300 text-sm">
                <p>
                  <strong>LexChat</strong> is an intelligent legal research assistant designed to help legal professionals and researchers quickly access UK legislation and related case law.
                </p>

                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Purpose</h3>
                  <p>
                    To simplify the process of legal research by allowing natural language queries to retrieve specific sections of legislation and relevant case precedents.
                  </p>
                </div>

                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Data Sources</h3>
                  <ul className="list-disc list-inside">
                    <li><strong>The National Archives</strong> (legislation.gov.uk) for UK Legislation.</li>
                    <li><strong>The National Archives</strong> (caselaw.nationalarchives.gov.uk) for Case Law.</li>
                  </ul>
                </div>

                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">AI Approach</h3>
                  <p>
                    LexChat utilizes an <strong>Agentic RAG</strong> architecture powered by the <strong>Model Context Protocol (MCP)</strong>. It intelligently queries external legal databases to retrieve relevant legislation and case law, which are then analyzed by a Large Language Model to provide accurate, context-aware answers.
                  </p>
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setShowAbout(false)}
                  className="bg-legal-blue text-white px-4 py-2 rounded-md hover:bg-blue-800 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )
      }

      {/* Admin Portal Modal */}
      {
        showAdminModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full h-[90vh] overflow-y-auto shadow-xl relative">
              <button
                onClick={() => setShowAdminModal(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <AdminPortal />
            </div>
          </div>
        )
      }

      {/* Settings Modal */}
      {
        showSettingsModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-lg w-full shadow-xl relative">
              <button
                onClick={() => setShowSettingsModal(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <Settings />
            </div>
          </div>
        )
      }

    </div >
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
