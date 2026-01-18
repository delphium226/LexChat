import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { marked } from 'marked';
import { rateMessage } from '../services/api';

import CommentModal from './CommentModal';

const ChatMessage = ({ message, onResend, showThinking }) => {
    const isUser = message.role === 'user';
    const isTool = message.role === 'tool';
    const [copied, setCopied] = useState(false);
    const [rating, setRating] = useState(message.rating || 0);
    const [isRating, setIsRating] = useState(false);
    const [comment, setComment] = useState(message.feedback_comment || '');
    const [showCommentModal, setShowCommentModal] = useState(false);

    const handleRate = async (value) => {
        if (!message.id) return;
        setIsRating(true);
        try {
            await rateMessage(message.id, value, comment); // Send existing comment if any
            setRating(value);
        } catch (error) {
            console.error('Failed to rate message', error);
        } finally {
            setIsRating(false);
        }
    };

    const handleCommentSubmit = async (newComment) => {
        if (!message.id) return;
        setIsRating(true);
        try {
            await rateMessage(message.id, rating, newComment);
            setComment(newComment);
            setShowCommentModal(false);
        } catch (error) {
            console.error('Failed to save comment', error);
        } finally {
            setIsRating(false);
        }
    };

    const processedContent = useMemo(() => {
        let content = message.content;
        if (!content) return '';

        // Regex for complete thinking blocks
        const thinkBlockRegex = /<(think|thinking)>([\s\S]*?)<\/\1>/gi;

        // Regex for unclosed thinking block (usually at the start or during streaming)
        const unclosedThinkRegex = /<(think|thinking)>([\s\S]*)$/i;

        if (showThinking) {
            // Replace complete blocks with * content * (italics)
            content = content.replace(thinkBlockRegex, (match, tag, innerContent) => `\n*${innerContent.trim()}*\n`);

            // Replace unclosed block
            content = content.replace(unclosedThinkRegex, (match, tag, innerContent) => `\n*${innerContent.trim()}*`);

            return content;
        } else {
            // Remove complete blocks
            content = content.replace(thinkBlockRegex, '');

            // Remove unclosed block
            content = content.replace(unclosedThinkRegex, '');

            return content.trim();
        }
    }, [message.content, showThinking]);

    const handleCopy = async () => {
        try {
            const htmlContent = await marked(processedContent);
            const blobHtml = new Blob([htmlContent], { type: 'text/html' });
            const blobText = new Blob([processedContent], { type: 'text/plain' });

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
            navigator.clipboard.writeText(processedContent);
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
                className={`rounded-lg max-w-3xl shadow-md overflow-hidden ${isUser
                    ? 'bg-legal-blue text-white'
                    : 'bg-white text-gray-800 border border-gray-200 dark:bg-black dark:text-white dark:border-gray-700'
                    }`}
            >
                <div className={`p-4 prose prose-sm max-w-none ${isUser ? 'prose-invert text-white' : 'dark:prose-invert dark:text-white'}`}>
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                            a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />
                        }}
                    >
                        {processedContent}
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
                    <div className="bg-gray-50 dark:bg-gray-900/50 p-2 px-4 flex justify-between items-center border-t border-gray-100 dark:border-gray-800">
                        {/* Rating Widget */}
                        <div className="flex items-center space-x-2">
                            <div className="flex items-center space-x-1">
                                <span className="text-xs text-gray-500 dark:text-gray-400 mr-1">Rate:</span>
                                {[1, 2, 3, 4, 5].map((star) => (
                                    <button
                                        key={star}
                                        onClick={() => handleRate(star)}
                                        disabled={!message.id || isRating}
                                        className={`focus:outline-none transition-colors ${star <= rating ? 'text-yellow-400' : 'text-gray-300 dark:text-gray-600 hover:text-yellow-200'
                                            }`}
                                        title={`Rate ${star} star${star > 1 ? 's' : ''}`}
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                                            <path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clipRule="evenodd" />
                                        </svg>
                                    </button>
                                ))}
                            </div>

                            {/* Comment Icon Button */}
                            <button
                                onClick={() => setShowCommentModal(true)}
                                className={`ml-2 p-1 rounded-full transition-colors ${comment ? 'text-blue-500 hover:text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}
                                title={comment ? "Edit comment" : "Add comment"}
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                                </svg>
                            </button>
                        </div>

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

            <CommentModal
                isOpen={showCommentModal}
                onClose={() => setShowCommentModal(false)}
                onSubmit={handleCommentSubmit}
                initialComment={comment}
            />
        </div>
    );
};

export default ChatMessage;
