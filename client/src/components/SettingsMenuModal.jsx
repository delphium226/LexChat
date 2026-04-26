import React from 'react';

const SettingsMenuModal = ({
    isOpen,
    onClose,
    user,
    darkMode,
    onToggleDarkMode,
    onOpenAccountSettings,
    onOpenAdminPortal,
    onOpenAbout,
    onGiveFeedback,
    onLogout
}) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" onClick={onClose}>
            <div
                className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-sm overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
                    <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Settings</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-2">
                    {/* Account Settings */}
                    <button
                        onClick={() => { onOpenAccountSettings(); onClose(); }}
                        className="w-full text-left px-4 py-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 transition-colors flex items-center gap-3"
                    >

                        <span className="font-medium">Account Settings</span>
                    </button>

                    {/* Admin Portal (Conditional) */}
                    {user.role === 'admin' && (
                        <button
                            onClick={() => { onOpenAdminPortal(); onClose(); }}
                            className="w-full text-left px-4 py-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 transition-colors flex items-center gap-3"
                        >

                            <span className="font-medium">Admin Portal</span>
                        </button>
                    )}

                    <div className="border-t border-gray-100 dark:border-gray-700 my-1 mx-2"></div>

                    {/* Dark Mode Toggle */}
                    <div
                        className="flex items-center justify-between px-4 py-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors group"
                        onClick={onToggleDarkMode}
                    >
                        <div className="flex items-center gap-3">

                            <span className="font-medium text-gray-700 dark:text-gray-200">Dark Mode</span>
                        </div>
                        <div
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${darkMode ? 'bg-legal-blue' : 'bg-gray-300'}`}
                        >
                            <span
                                className={`${darkMode ? 'translate-x-6' : 'translate-x-1'} inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
                            />
                        </div>
                    </div>

                    {/* About */}
                    <button
                        onClick={() => { onOpenAbout(); onClose(); }}
                        className="w-full text-left px-4 py-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 transition-colors flex items-center gap-3"
                    >

                        <span className="font-medium">About LexChat</span>
                    </button>

                    {onGiveFeedback && (
                        <button
                            onClick={() => { onGiveFeedback(); onClose(); }}
                            className="w-full text-left px-4 py-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 transition-colors flex items-center gap-3"
                        >
                            <span className="font-medium">Give Feedback</span>
                        </button>
                    )}

                    <div className="border-t border-gray-100 dark:border-gray-700 my-1 mx-2"></div>

                    {/* Logout */}
                    <button
                        onClick={onLogout}
                        className="w-full text-left px-4 py-3 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 transition-colors flex items-center gap-3"
                    >

                        <span className="font-medium">Log Out</span>
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SettingsMenuModal;
