import React from 'react';

const Hourglass = () => (
    <svg
        className="w-6 h-6 animate-hourglass text-blue-500 dark:text-blue-400"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
    >
        <path d="M12 12C9 12 7 8 7 4H17C17 8 15 12 12 12Z" fill="currentColor" opacity="0.2" />
        <path d="M12 12C15 12 17 16 17 20H7C7 16 9 12 12 12Z" fill="currentColor" opacity="0.2" />
        <path d="M7 4H17M7 20H17M7 4C7 8 9 12 12 12C15 12 17 8 17 4M7 20C7 16 9 12 12 12C15 12 17 16 17 20" />
    </svg>
);

export default Hourglass;
