import React, { useState, useEffect, useRef } from 'react';
import { sendMessage, createChat, getChatMessages, saveMessage, updatePreferences, submitFeedback, getModels } from './services/api';
import ChatMessage from './components/ChatMessage';
import loadingGif from './assets/load-35_128.gif';
import Hourglass from './components/Hourglass';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginModal from './components/LoginModal';
import AdminPortal from './pages/AdminPortal';
import Settings from './pages/Settings';
import HistoryModal from './components/HistoryModal';
import SettingsMenuModal from './components/SettingsMenuModal';

// ---------------------------------------------------------------------------
// Feedback Modal
// ---------------------------------------------------------------------------
const FeedbackModal = ({ onClose }) => {
  const [text, setText] = React.useState('');
  const [status, setStatus] = React.useState('idle'); // idle | submitting | success | error

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setStatus('submitting');
    try {
      await submitFeedback(text.trim());
      setStatus('success');
    } catch {
      setStatus('error');
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-lg w-full shadow-xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">Give Feedback</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 focus:outline-none text-xl leading-none">&times;</button>
        </div>

        {status === 'success' ? (
          <div className="text-center py-6">
            <p className="text-green-600 dark:text-green-400 font-medium text-lg mb-2">Thank you for your feedback!</p>
            <p className="text-gray-500 dark:text-gray-400 text-sm mb-6">Your response has been recorded and will be reviewed by the team.</p>
            <button onClick={onClose} className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium">Close</button>
          </div>
        ) : (
          <>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Share any thoughts, suggestions, or issues you've encountered with LexChat. Your feedback helps improve the system for everyone.
            </p>
            <textarea
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md p-3 text-sm dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={6}
              placeholder="Describe your experience, suggest a feature, or report a problem..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={status === 'submitting'}
              autoFocus
            />
            {status === 'error' && (
              <p className="text-red-500 text-xs mt-2">Something went wrong. Please try again.</p>
            )}
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors">Cancel</button>
              <button
                onClick={handleSubmit}
                disabled={!text.trim() || status === 'submitting'}
                className="px-5 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === 'submitting' ? 'Submitting…' : 'Submit Feedback'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

function AppContent() {
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');

  const [selectedModel, setSelectedModel] = useState('');
  const [selectedModelContext, setSelectedModelContext] = useState(256 * 1024);
  const [activeProvider, setActiveProvider] = useState('ollama');
  const [loading, setLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState('');
  const [contextUsage, setContextUsage] = useState(null);
  const [showAbout, setShowAbout] = useState(false);
  const [showThinking, setShowThinking] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 768; // 768px is tailwind 'md' breakpoint
    }
    return false;
  });

  const [currentView, setCurrentView] = useState('chat'); // 'chat', 'admin', 'settings'
  const [currentChatId, setCurrentChatId] = useState(null);

  // Modals State
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showAdminModal, setShowAdminModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);

  // Dark Mode State
  const [darkMode, setDarkMode] = useState(() => {
    // If user is loaded, use their preference, otherwise localstorage, otherwise system/false
    if (user && user.dark_mode !== undefined) {
      return user.dark_mode;
    }
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('darkMode');
      if (saved !== null) {
        return saved === 'true';
      }
    }
    return false;
  });

  // Sync dark mode when user logs in
  useEffect(() => {
    if (user && user.dark_mode !== undefined) {
      setDarkMode(user.dark_mode);
    }
  }, [user]);

  const [showSettings, setShowSettings] = useState(false);
  const [showSettingsMenu, setShowSettingsMenu] = useState(false);


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
    getModels().then((models) => {
      if (models && models.length > 0) {
        setSelectedModel(models[0].name);
        setSelectedModelContext(models[0].context_length || 256 * 1024);
        setActiveProvider(models[0].provider || 'ollama');
      }
    }).catch(() => {
      // Fallback if models endpoint fails
      setSelectedModel('mistral-large-3:675b-cloud');
      setSelectedModelContext(256 * 1024);
    });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentStatus]); // Scroll on status update too

  // Animate favicon while loading — GIFs don't animate in Chrome/Edge,
  // so we drive a canvas spinner via requestAnimationFrame instead.
  useEffect(() => {
    const favicon = document.querySelector("link[rel='icon']");
    if (!favicon) return;

    if (!loading) {
      favicon.href = '/favicon.png';
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');
    let animationId;
    let startTime = null;

    const draw = (timestamp) => {
      if (!startTime) startTime = timestamp;
      const angle = ((timestamp - startTime) / 700) * Math.PI * 2;

      ctx.clearRect(0, 0, 32, 32);

      // Track ring
      ctx.beginPath();
      ctx.arc(16, 16, 12, 0, Math.PI * 2);
      ctx.strokeStyle = '#dbeafe';
      ctx.lineWidth = 3.5;
      ctx.stroke();

      // Spinning arc
      ctx.beginPath();
      ctx.arc(16, 16, 12, angle, angle + Math.PI * 1.25);
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 3.5;
      ctx.lineCap = 'round';
      ctx.stroke();

      favicon.href = canvas.toDataURL('image/png');
      animationId = requestAnimationFrame(draw);
    };

    animationId = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animationId);
      favicon.href = '/favicon.png';
    };
  }, [loading]);

  // Reset state when user logs out or changes
  useEffect(() => {
    if (!user) {
      setMessages([]);
      setInput('');
      setCurrentChatId(null);
      setContextUsage(null);
      setAgentStatus('');
      setLoading(false);
      setShowSettingsMenu(false);
      setShowHistoryModal(false);
      setShowAdminModal(false);
      setShowSettingsModal(false);
    }
  }, [user]);

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

    let activeChatId = currentChatId;

    try {
      // 1. Create chat if doesn't exist
      if (!activeChatId) {
        try {
          const title = contentToSend.slice(0, 30) + (contentToSend.length > 30 ? '...' : '');
          const newChat = await createChat(title, selectedModel, activeProvider);
          activeChatId = newChat.id;
          setCurrentChatId(activeChatId);
        } catch (err) {
          console.error('Failed to create chat:', err);
          // Proceed without history if DB fails? 
          // Ideally we should alert but for now let's just log.
        }
      }

      // 2. Persist User Message
      if (activeChatId) {
        try {
          await saveMessage(activeChatId, 'user', contentToSend);
        } catch (err) {
          console.error('Failed to save user message:', err);
        }
      }

      // Send the message history including the new user message
      // Note: `messages` here refers to the state *before* the current userMsg was added to the UI.
      // The `userMsg` is explicitly added to `messagesToSend`.
      const messagesToSend = [...messages, userMsg];

      const contextLength = selectedModelContext;

      const response = await sendMessage(messagesToSend, selectedModel, contextLength, (status) => {
        if (status.type === 'tool_start') {
          const toolMessages = {
            'Research Agent': 'Delegating to research agent...',
            'Worker: search_legislation': 'Querying National Legislation Archives...',
            'Worker: get_legislation_text': 'Reviewing statutory text in detail...',

            'search_legislation': 'Querying National Legislation Archives...',
            'get_legislation_text': 'Reviewing statutory text in detail...',

          };
          setAgentStatus(toolMessages[status.tool] || `${status.tool}...`);
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
        } else if (status.type === 'queue') {
          setAgentStatus(status.message);
        } else if (status.type === 'warning') {
          setAgentStatus(status.message);
        }
      }, controller.signal);

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

      // 3. Persist Assistant Message
      if (activeChatId) {
        try {
          const savedMsg = await saveMessage(activeChatId, 'assistant', response.content);
          // Update state with the saved message (which has ID) to enable ratings
          setMessages(prev => {
            const updated = [...prev];
            // Find the last assistant message and replace it
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'assistant' && !updated[i].id) {
                updated[i] = savedMsg;
                break;
              }
            }
            return updated;
          });

        } catch (err) {
          console.error('Failed to save assistant message:', err);
        }
      }

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
    setCurrentChatId(null);
  };

  const loadChat = async (chatId, model) => {
    try {
      setLoading(true);
      const msgs = await getChatMessages(chatId);
      // Convert DB messages to UI format if needed (DB: role, content. UI: same)
      // DB messages might have extra fields like created_at, id.
      // The UI expects { role, content, ... }
      setMessages(msgs);
      setCurrentChatId(chatId);
      if (model) {
        setSelectedModel(model);
      }
      setShowHistoryModal(false);
      setContextUsage(null); // Reset usage context as we don't store it yet
    } catch (error) {
      console.error("Failed to load chat", error);
    } finally {
      setLoading(false);
    }
  };

  // Helper to calculate usage percentage
  const getUsagePercentage = () => {
    const total = contextUsage ? (contextUsage.prompt_eval_count || 0) : 0;
    return Math.min((total / selectedModelContext) * 100, 100);
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
        <div className="flex items-center justify-center gap-1.5 mb-2">
          <img src="/favicon.png" alt="LexChat" className="w-10 h-10" />
          <h1 className="text-3xl font-bold text-blue-600 tracking-tight">LexChat</h1>
        </div>

        <div className="h-10" />

        <button
          onClick={() => { handleNewChat(); }}
          className="w-full text-center p-2 rounded-md mb-2 hover:bg-blue-700 transition-colors font-medium bg-blue-600 text-white text-lg"
        >
          New chat
        </button>

        <button
          onClick={() => setShowHistoryModal(true)}
          className="w-full text-center p-2 rounded-md mb-2 hover:bg-blue-700 transition-colors font-medium bg-blue-600 text-white text-lg"
        >
          History
        </button>

        <button
          onClick={() => setShowFeedbackModal(true)}
          className="w-full text-center p-2 rounded-md mb-6 hover:bg-blue-700 transition-colors font-medium bg-blue-600 text-white text-lg"
        >
          Give feedback
        </button>







        {/* Context Usage Graph */}
        {
          selectedModel && (
            <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className="text-xs font-semibold text-gray-500 dark:text-white uppercase tracking-wider mb-2">Chat Memory</h3>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 mb-2">
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
                <span>{contextUsage ? (contextUsage.prompt_eval_count || 0) : 0} tokens</span>
                <span>{formatContextLength(selectedModelContext)} limit</span>
              </div>

            </div>
          )
        }


        {/* Global Sidebar Footer Items */}
        <div className="mt-auto">


          <button
            onClick={() => setShowSettingsMenu(!showSettingsMenu)}
            className={`flex items-center justify-center w-full p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors font-medium ${showSettingsMenu ? 'bg-gray-200 dark:bg-gray-700 text-legal-blue' : 'text-gray-700 dark:text-gray-300'}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6 mr-2 flex-shrink-0">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
            {user.username}
          </button>
        </div>
      </div>



      {/* Main Content Area */}
      < div className="flex-1 flex flex-col relative w-full overflow-hidden" >
        {/* Sidebar Toggle Button */}
        < button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)
          }
          style={{ left: isSidebarOpen ? 'calc(16rem - 15.5px)' : '15.5px' }}
          className="fixed top-[47px] z-40 p-[7px] bg-gray-200 dark:bg-gray-700 dark:text-white rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 transition-[left] duration-300 shadow-sm"
          title={isSidebarOpen ? "Collapse Sidebar" : "Expand Sidebar"}
        >
          {
            isSidebarOpen ? (
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-[17px] h-[17px]" >
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-[12px] h-[12px]">
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
                {agentStatus && agentStatus.toLowerCase().includes('queue') ? (
                  <Hourglass />
                ) : (
                  <img src={loadingGif} alt="Processing..." className="w-6 h-6 flex-shrink-0" />
                )}
                <span className="text-xs text-white dark:text-gray-200 truncate">{agentStatus || 'Agent is thinking...'}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-[#8c8e91] dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 z-40 relative">
          <form
            className="flex space-x-4"
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
          <p className="text-center text-xs text-gray-300 dark:text-gray-500 mt-2">LexChat is AI and can make mistakes. Please verify information before using.</p>
        </div>


      </div >
      {/* Feedback Modal */}
      {showFeedbackModal && (
        <FeedbackModal onClose={() => setShowFeedbackModal(false)} />
      )}

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
                  <strong>LexChat</strong> is an intelligent legal research assistant designed to help legal professionals and researchers quickly access UK legislation.
                </p>

                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Purpose</h3>
                  <p>
                    To simplify the process of legal research by allowing natural language queries to retrieve specific sections of legislation.
                  </p>
                </div>

                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Data Sources</h3>
                  <ul className="list-disc list-inside">
                    <li><strong>The National Archives</strong> (legislation.gov.uk) for UK Legislation.</li>

                  </ul>
                </div>

                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-1">AI Approach</h3>
                  <p>
                    LexChat utilizes an <strong>Agentic RAG</strong> architecture powered by the <strong>Model Context Protocol (MCP)</strong>. It intelligently queries external legal databases to retrieve relevant legislation, which are then analyzed by a Large Language Model to provide accurate, context-aware answers.
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
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-[95vw] h-[95vh] overflow-y-auto shadow-xl relative">
              <button
                onClick={() => setShowAdminModal(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <AdminPortal currentUser={user} />
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

      {/* History Modal */}
      {
        showHistoryModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-gray-800 rounded-lg max-w-lg w-full h-[80vh] shadow-xl relative overflow-hidden">
              <HistoryModal
                onClose={() => setShowHistoryModal(false)}
                onSelectChat={loadChat}
              />
            </div>
          </div>
        )
      }

      {/* Settings Menu Modal */}
      <SettingsMenuModal
        isOpen={showSettingsMenu}
        onClose={() => setShowSettingsMenu(false)}
        user={user}
        darkMode={darkMode}
        onToggleDarkMode={async () => {
          const newMode = !darkMode;
          setDarkMode(newMode);
          try {
            await updatePreferences({ dark_mode: newMode });
          } catch (e) {
            console.error("Failed to save preference", e);
          }
        }}
        onOpenAccountSettings={() => setShowSettingsModal(true)}
        onOpenAdminPortal={() => setShowAdminModal(true)}
        onOpenAbout={() => setShowAbout(true)}
        onLogout={logout}
      />
    </div >
  );
}

import { Routes, Route } from 'react-router-dom';
import SystemChat from './pages/SystemChat';

// ... existing imports ...

// ... AppContent code ...

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<AppContent />} />
        <Route path="/systemchat" element={<SystemChat />} />
      </Routes>
    </AuthProvider>
  );
}
