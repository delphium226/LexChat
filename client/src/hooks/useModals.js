import { useReducer } from 'react';

// Visibility state for the top-level dialogs, moved from App.jsx. Consolidates
// the boolean flags (previously one useState pair each) into one reducer.
// API: modals.<name> (bool), modals.open(name), modals.close(name),
// modals.closeAll(). Names: settingsMenu, admin, settings, history, about,
// dataSources, weeklyBanner, sessionFeedback.
const MODAL_NAMES = [
  'settingsMenu',
  'admin',
  'settings',
  'history',
  'about',
  'dataSources',
  'weeklyBanner',
  'sessionFeedback',
];

const initialState = MODAL_NAMES.reduce((acc, name) => ({ ...acc, [name]: false }), {});

function reducer(state, action) {
  switch (action.type) {
    case 'open':
      return { ...state, [action.modal]: true };
    case 'close':
      return { ...state, [action.modal]: false };
    case 'closeAll':
      return initialState;
    default:
      return state;
  }
}

export function useModals() {
  const [state, dispatch] = useReducer(reducer, initialState);
  return {
    ...state,
    open: modal => dispatch({ type: 'open', modal }),
    close: modal => dispatch({ type: 'close', modal }),
    closeAll: () => dispatch({ type: 'closeAll' }),
  };
}
