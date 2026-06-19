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
    onOpenDataSources,
    onLogout,
    botName = 'AILA',
}) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={onClose}>
            <div
                className="bg-paper rounded-lg shadow-xl border border-ink-200 w-full max-w-sm overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-4 border-b border-ink-200 flex justify-between items-center">
                    <h2 className="text-lg font-semibold text-ink-800">Settings</h2>
                    <button
                        onClick={onClose}
                        className="size-[30px] flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                        aria-label="Close"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-2">
                    {/* Account Settings */}
                    <button
                        onClick={() => { onOpenAccountSettings(); onClose(); }}
                        className="w-full text-left px-4 py-3 rounded-md hover:bg-ink-100 text-ink-700 transition-colors flex items-center gap-3"
                    >
                        <span className="font-medium">Account Settings</span>
                    </button>

                    {/* Admin Portal (Conditional) */}
                    {user.role === 'admin' && (
                        <button
                            onClick={() => { onOpenAdminPortal(); onClose(); }}
                            className="w-full text-left px-4 py-3 rounded-md hover:bg-ink-100 text-ink-700 transition-colors flex items-center gap-3"
                        >
                            <span className="font-medium">Admin Portal</span>
                        </button>
                    )}

                    <div className="border-t border-ink-100 my-1 mx-2"></div>

                    {/* Dark Mode Toggle */}
                    <div
                        className="flex items-center justify-between px-4 py-3 rounded-md hover:bg-ink-100 cursor-pointer transition-colors group"
                        onClick={onToggleDarkMode}
                    >
                        <div className="flex items-center gap-3">
                            <span className="font-medium text-ink-700">Dark Mode</span>
                        </div>
                        <div
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${darkMode ? 'bg-accent' : 'bg-ink-300'}`}
                        >
                            <span
                                className={`${darkMode ? 'translate-x-6' : 'translate-x-1'} inline-block h-4 w-4 transform rounded-full bg-paper transition-transform`}
                            />
                        </div>
                    </div>

                    {/* Data Sources */}
                    <button
                        onClick={() => { onOpenDataSources(); onClose(); }}
                        className="w-full text-left px-4 py-3 rounded-md hover:bg-ink-100 text-ink-700 transition-colors flex items-center gap-3"
                    >
                        <span className="font-medium">Data Sources</span>
                    </button>

                    {/* About */}
                    <button
                        onClick={() => { onOpenAbout(); onClose(); }}
                        className="w-full text-left px-4 py-3 rounded-md hover:bg-ink-100 text-ink-700 transition-colors flex items-center gap-3"
                    >
                        <span className="font-medium">About {botName}</span>
                    </button>

                    <div className="border-t border-ink-100 my-1 mx-2"></div>

                    {/* Logout */}
                    <button
                        onClick={onLogout}
                        className="w-full text-left px-4 py-3 rounded-md hover:bg-danger-soft text-danger transition-colors flex items-center gap-3"
                    >
                        <span className="font-medium">Log Out</span>
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SettingsMenuModal;
