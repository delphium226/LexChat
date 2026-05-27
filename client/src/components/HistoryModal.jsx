import React, { useEffect, useState } from 'react';
import { getChats, deleteChat, updateChatTitle } from '../services/api';

const HistoryModal = ({ onClose, onSelectChat }) => {
    const [chats, setChats] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState(null);
    const [editTitle, setEditTitle] = useState('');
    const [searchQuery, setSearchQuery] = useState('');

    useEffect(() => {
        loadChats();
    }, []);

    const loadChats = async () => {
        try {
            const data = await getChats();
            setChats(data);
        } catch (error) {
            console.error('Failed to load chats:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (e, chatId) => {
        e.stopPropagation();
        if (!window.confirm('Are you sure you want to delete this chat?')) return;

        try {
            await deleteChat(chatId);
            setChats(chats.filter(c => c.id !== chatId));
        } catch (error) {
            console.error('Failed to delete chat:', error);
        }
    };

    const startEditing = (e, chat) => {
        e.stopPropagation();
        setEditingId(chat.id);
        setEditTitle(chat.title);
    };

    const saveTitle = async (e) => {
        e.stopPropagation();
        if (!editTitle.trim()) return;

        try {
            await updateChatTitle(editingId, editTitle);
            setChats(chats.map(c => c.id === editingId ? { ...c, title: editTitle } : c));
            setEditingId(null);
        } catch (error) {
            console.error('Failed to update title:', error);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            saveTitle(e);
        } else if (e.key === 'Escape') {
            setEditingId(null);
        }
    };

    const filteredChats = chats.filter(c =>
        c.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex flex-col h-full w-full bg-paper rounded-lg overflow-hidden relative">
            <div className="p-4 border-b border-ink-200 flex justify-between items-center">
                <h2 className="text-xl font-bold text-ink-900">Chat History</h2>
                <button
                    onClick={onClose}
                    className="size-[30px] flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                    aria-label="Close"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>

            <div className="px-4 pt-3 pb-1">
                <div className="relative">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-400 pointer-events-none">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 104.5 4.5a7.5 7.5 0 0012.15 12.15z" />
                    </svg>
                    <input
                        type="text"
                        placeholder="Search chats…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-9 pr-4 py-2 text-sm border border-ink-200 rounded-lg bg-ink-50 text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-accent"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery('')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                            aria-label="Clear search"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    )}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
                {loading ? (
                    <div className="text-center text-ink-500 mt-4">Loading history...</div>
                ) : filteredChats.length === 0 ? (
                    <div className="text-center text-ink-500 mt-4">
                        {searchQuery ? 'No chats match your search.' : 'No chat history found.'}
                    </div>
                ) : (
                    <div className="space-y-2">
                        {filteredChats.map(chat => (
                            <div
                                key={chat.id}
                                onClick={() => onSelectChat(chat.id, chat.model)}
                                title={chat.title}
                                className="relative flex items-center p-3 rounded-lg border border-ink-200 hover:bg-ink-50 cursor-pointer transition-colors group w-full"
                            >
                                <div className="flex-1 min-w-0 pr-2">
                                    {editingId === chat.id ? (
                                        <input
                                            type="text"
                                            value={editTitle}
                                            onChange={(e) => setEditTitle(e.target.value)}
                                            onKeyDown={handleKeyDown}
                                            onBlur={() => setEditingId(null)}
                                            autoFocus
                                            className="w-full px-2 py-1 text-sm border border-ink-200 rounded bg-paper text-ink-900"
                                            onClick={(e) => e.stopPropagation()}
                                        />
                                    ) : (
                                        <div>
                                            <div className="font-medium text-ink-900 truncate">
                                                {chat.title}
                                            </div>
                                            <div className="text-xs text-ink-500">
                                                {new Date(chat.created_at).toLocaleString()}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity bg-ink-50 rounded pl-1">
                                    <button
                                        onClick={(e) => startEditing(e, chat)}
                                        className="p-1 mr-1 rounded-md text-ink-400 hover:text-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                                        title="Rename"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                                        </svg>
                                    </button>
                                    <button
                                        onClick={(e) => handleDelete(e, chat.id)}
                                        className="p-1 rounded-md text-ink-400 hover:text-danger transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
                                        title="Delete"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="p-4 border-t border-ink-200 bg-ink-50 rounded-b-lg flex justify-end">
                <button
                    onClick={onClose}
                    className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
                >
                    Close
                </button>
            </div>
        </div>
    );
};

export default HistoryModal;
