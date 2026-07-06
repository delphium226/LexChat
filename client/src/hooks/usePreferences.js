import { useState, useEffect } from 'react';

// User preferences (dark mode, chat mode, research mode), moved from App.jsx.
// localStorage holds the pre-login default; the user's saved preferences from
// the API override on login; the dark class on <html> tracks darkMode.
export function usePreferences(user) {
  const [chatMode, setChatMode] = useState('research');
  const [researchMode, setResearchMode] = useState('legislation_only');
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('darkMode');
      if (saved !== null) return saved === 'true';
    }
    return false;
  });

  // Sync saved preferences from the API on login (moved verbatim from App.jsx;
  // the sync must overwrite local state, so setState-in-effect is intended here).
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!user) return;
    if (user.dark_mode !== undefined) setDarkMode(user.dark_mode);
    if (user.research_mode) setResearchMode(user.research_mode);
    if (user.chat_mode) setChatMode(user.chat_mode);
  }, [user]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (darkMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode]);

  return { chatMode, setChatMode, researchMode, setResearchMode, darkMode, setDarkMode };
}
