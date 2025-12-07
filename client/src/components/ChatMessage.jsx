import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { marked } from 'marked';

const ChatMessage = ({ message, onResend }) => {
    const isUser = message.role === 'user';
    const isTool = message.role === 'tool';
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            const htmlContent = await marked(message.content);
            const blobHtml = new Blob([htmlContent], { type: 'text/html' });
            const blobText = new Blob([message.content], { type: 'text/plain' });

            const data = [new ClipboardItem({
                ['text/html']: blobHtml,
                ['text/plain']: blobText,
            })];

            await navigator.clipboard.write(data);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy: ', err);
            // Fallback to simple text copy if rich copy fails
            navigator.clipboard.writeText(message.content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    if (isTool) {
        // Optional: Hide tool outputs or show them in a collapsible detail
        return (
            <div className="flex justify-start mb-4">
                <div className="bg-gray-300 text-gray-700 text-xs p-2 rounded-lg max-w-3xl font-mono">
                    <strong>Tool Output ({message.name}):</strong> <span className="italic">Hidden for brevity (check console)</span>
                </div>
            </div>
        );
    }

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
            <div
                className={`p-4 rounded-lg max-w-3xl shadow-md ${isUser
                    ? 'bg-legal-blue text-white'
                    : 'bg-white text-gray-800 border border-gray-200'
                    }`}
            >
                <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert text-white' : ''}`}>
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                            a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />
                        }}
                    >
                        {message.content}
                    </ReactMarkdown>
                </div>
                {message.tool_calls && (
                    <div className="mt-2 text-xs opacity-75 border-t pt-2 border-gray-300">
                        <span className="font-semibold">Used Tools:</span>
                        <ul className="list-disc pl-4">
                            {message.tool_calls.map((tc, i) => (
                                <li key={i}>{tc.function.name}</li>
                            ))}
                        </ul>
                    </div>
                )}
                {!isUser && (
                    <div className="mt-3 flex justify-end border-t border-gray-100 pt-2">
                        <button
                            onClick={handleCopy}
                            className="text-xs text-gray-500 hover:text-legal-blue transition-colors flex items-center gap-1"
                            title="Copy to clipboard"
                        >
                            {copied ? (
                                <span className="text-green-600 font-medium">Copied!</span>
                            ) : (
                                <>
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5" />
                                    </svg>
                                </>
                            )}
                        </button>
                    </div>
                )}
                {isUser && (
                    <div className="mt-2 flex justify-end gap-3 border-t border-white/20 pt-2">
                        <button
                            onClick={handleCopy}
                            className="text-white/70 hover:text-white transition-colors"
                            title="Copy to clipboard"
                        >
                            {copied ? (
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                            ) : (
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5" />
                                </svg>
                            )}
                        </button>
                        <button
                            onClick={onResend}
                            className="text-white/70 hover:text-white transition-colors"
                            title="Re-run query"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                            </svg>
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ChatMessage;
