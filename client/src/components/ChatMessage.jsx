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
                className={`rounded-lg max-w-[90%] shadow-md overflow-hidden min-w-[150px] ${isUser
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
                        {/* Rating/Feedback Button */}
                        <div className="flex items-center">
                            <button
                                onClick={() => setShowCommentModal(true)}
                                className={`text-xs px-2 py-1 rounded transition-colors flex items-center gap-1 ${rating > 0
                                    ? 'text-yellow-600 bg-yellow-50 dark:text-yellow-400 dark:bg-yellow-900/30'
                                    : 'text-gray-500 hover:text-legal-blue hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
                                    }`}
                            >
                                {rating > 0 ? (
                                    <>
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
                                            <path fillRule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clipRule="evenodd" />
                                        </svg>
                                        <span>{rating} Stars</span>
                                    </>
                                ) : (
                                    <span>Rate this answer</span>
                                )}
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
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5" />
                                    </svg>
                                </>
                            )}
                        </button>
                    </div>
                )}
                {isUser && (
                    <div className="mt-2 flex justify-end gap-3 border-t border-white/20 pt-2 px-4 pb-2">
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
                rating={rating}
                onRate={handleRate}
            />
        </div>
    );
};

export default ChatMessage;
