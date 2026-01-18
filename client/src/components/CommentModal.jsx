import React, { useState, useEffect } from 'react';

const CommentModal = ({ isOpen, onClose, onSubmit, initialComment = '' }) => {
    const [comment, setComment] = useState(initialComment);

    useEffect(() => {
        setComment(initialComment);
    }, [initialComment, isOpen]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-lg w-full shadow-xl relative animate-fadeIn">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Provide Feedback</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 focus:outline-none">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <textarea
                    className="w-full h-32 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-legal-blue dark:bg-gray-700 dark:border-gray-600 dark:text-white dark:placeholder-gray-400 resize-none"
                    placeholder="Enter your detailed feedback here..."
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    autoFocus
                />

                <div className="mt-4 flex justify-end gap-2">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={() => onSubmit(comment)}
                        className="px-4 py-2 text-sm bg-legal-blue text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                        Save Comment
                    </button>
                </div>
            </div>
        </div>
    );
};

export default CommentModal;
