import { useState, useEffect } from 'react';
import { getFeatures, getMatters } from '../services/api';

// Matters state (the feature flag, open/closed matter lists, sidebar
// expand/collapse, and the create/notes/assign modal flags), moved from
// App.jsx. The matter list is refetched on login and whenever the active chat
// changes (mirroring the original combined chats+matters effect); the recent
// chat list stays in App.jsx as it is shared with the chat flow.
//
// Destructured to the same names the JSX already used, so no call sites change.
export function useMatters(user, currentChatId) {
  // Default new flags to true so mode options don't flash off before the flags
  // load; the API response replaces this whole object on login.
  const [features, setFeatures] = useState({
    matters_enabled: true,
    research_mode_enabled: true,
    deep_research_mode_enabled: true,
    suggested_questions_enabled: true,
  });
  const [matters, setMatters] = useState([]);
  const [closedMatters, setClosedMatters] = useState([]);
  const [showClosedMatters, setShowClosedMatters] = useState(false);
  const [expandedMatterIds, setExpandedMatterIds] = useState(new Set());
  const [showCreateMatterModal, setShowCreateMatterModal] = useState(false);
  const [notesModalMatter, setNotesModalMatter] = useState(null);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [assigningChatId, setAssigningChatId] = useState(null);

  // Fetch feature flags once on login
  useEffect(() => {
    if (!user) return;
    getFeatures()
      .then(setFeatures)
      .catch(err => console.warn('Failed to fetch feature flags:', err));
  }, [user]);

  // Reload matters whenever the active chat changes or the user logs in
  useEffect(() => {
    if (!user) return;
    if (features.matters_enabled)
      getMatters()
        .then(setMatters)
        .catch(err => console.warn('Failed to fetch matters:', err));
  }, [user, currentChatId, features.matters_enabled]);

  // Clear matters state on logout (called from App's reset effect)
  const resetMatters = () => {
    setMatters([]);
    setClosedMatters([]);
    setShowClosedMatters(false);
    setExpandedMatterIds(new Set());
  };

  return {
    features,
    matters,
    setMatters,
    closedMatters,
    setClosedMatters,
    showClosedMatters,
    setShowClosedMatters,
    expandedMatterIds,
    setExpandedMatterIds,
    showCreateMatterModal,
    setShowCreateMatterModal,
    notesModalMatter,
    setNotesModalMatter,
    showAssignModal,
    setShowAssignModal,
    assigningChatId,
    setAssigningChatId,
    resetMatters,
  };
}
