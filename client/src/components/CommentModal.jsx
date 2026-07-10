import React, { useState, useEffect } from 'react';
import Modal from './ui/Modal';

const CommentModal = ({ isOpen, onClose, onSubmit, initialComment = '', rating = 0, onRate }) => {
  const [comment, setComment] = useState(initialComment);

  useEffect(() => {
    setComment(initialComment);
  }, [initialComment, isOpen]);

  if (!isOpen) return null;

  return (
    <Modal onClose={onClose} className="max-w-lg w-full p-6">
      <div className="flex justify-between items-center mb-4">
          <h3 className="font-ui text-xl font-semibold text-ink-900">Rate & Feedback</h3>
          <button
            onClick={onClose}
            className="size-[30px] flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="Close"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-6 h-6"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Star Rating Section */}
        <div className="flex justify-center mb-6 items-center gap-2">
          <span className="font-ui text-sm font-medium text-ink-700">Rating -</span>
          <div className="flex space-x-2">
            {[1, 2, 3, 4, 5].map(star => (
              <button
                key={star}
                onClick={() => onRate(star)}
                className={`transition-colors transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded ${
                  star <= rating ? 'text-warn' : 'text-ink-300 hover:text-warn'
                }`}
                title={`Rate ${star} star${star > 1 ? 's' : ''}`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8">
                  <path
                    fillRule="evenodd"
                    d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            ))}
          </div>
        </div>

        <textarea
          className="w-full h-32 border border-ink-200 rounded-sm px-3 py-2 font-ui text-sm bg-paper text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent resize-none"
          placeholder="Enter your detailed feedback here..."
          value={comment}
          onChange={e => setComment(e.target.value)}
          autoFocus
        />

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Cancel
          </button>
          <button
            onClick={() => onSubmit(comment)}
            className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
          >
            Submit Feedback
          </button>
        </div>
    </Modal>
  );
};

export default CommentModal;
