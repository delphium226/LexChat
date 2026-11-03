// P4.9: show a mode change in the thread itself.
//
// Every saved assistant message records the modes it ran under
// (`research_mode`, `chat_mode`: the server's resolved values, echoed on the
// `result` event and stored on `messages`). When the user changes the research
// type or the chat mode, the backend tells the model (P4.1's marker on the
// user turn), but the legal professional saw nothing: the pills above the
// composer show the current setting only, so 6346's legal professional and
// the assistant disagreed for three turns about which control had changed.
//
// This finds, from the stored stamps alone, where the thread should say so.
// It follows the backend's rule (`mode_change_for`,
// server_py/src/utils/mode_change.py) exactly, so the thread shows the change
// the model was told about and no other:
//   - each assistant message is compared with the assistant message before
//     it, key by key; a key missing on either side (an older, unstamped row;
//     an error line) says nothing, never a change;
//   - Deep Research back to Conversational is silent: the client drops a chat
//     back to Conversational after every Deep Research run, so that is not the
//     user switching anything;
//   - a value with no label (not one of the UI's options) is not shown.
// Display only: nothing here reaches a request.
// Pure, so it is tested without a browser (`modeChange.test.js`).

import { CHAT_MODE_LABELS, RESEARCH_TYPE_LABELS } from '../constants/research.js';

const SILENT_CHAT_TRANSITIONS = new Set(['deep_research>conversational']);

const stamp = value => (typeof value === 'string' && value ? value : null);

// The phrases for one pair of stamped assistant messages, research type first
// as the backend's marker orders them. [] when nothing changed.
export function modeChangeParts(prev, next) {
  const parts = [];
  const rmFrom = stamp(prev?.research_mode);
  const rmTo = stamp(next?.research_mode);
  if (rmFrom && rmTo && rmFrom !== rmTo && RESEARCH_TYPE_LABELS[rmTo]) {
    parts.push({ control: 'research_type', from: rmFrom, to: rmTo, text: `Research type changed to ${RESEARCH_TYPE_LABELS[rmTo]}` });
  }
  const cmFrom = stamp(prev?.chat_mode);
  const cmTo = stamp(next?.chat_mode);
  if (
    cmFrom &&
    cmTo &&
    cmFrom !== cmTo &&
    !SILENT_CHAT_TRANSITIONS.has(`${cmFrom}>${cmTo}`) &&
    CHAT_MODE_LABELS[cmTo]
  ) {
    parts.push({ control: 'chat_mode', from: cmFrom, to: cmTo, text: `Mode changed to ${CHAT_MODE_LABELS[cmTo]}` });
  }
  return parts;
}

// Where the thread shows a change: a Map from the index of the message the
// marker sits above to its parts. The marker sits above the first user
// message after the earlier answer (the question the new setting was first
// used for), or above the later answer when no user message lies between.
// One marker per pair of answers, however many controls changed.
export function modeChangeMarkers(messages) {
  const out = new Map();
  if (!Array.isArray(messages)) return out;
  let prevIdx = -1;
  messages.forEach((m, i) => {
    if (!m || m.role !== 'assistant') return;
    if (prevIdx >= 0) {
      const parts = modeChangeParts(messages[prevIdx], m);
      if (parts.length) {
        let at = i;
        for (let k = prevIdx + 1; k < i; k++) {
          if (messages[k]?.role === 'user') {
            at = k;
            break;
          }
        }
        out.set(at, parts);
      }
    }
    prevIdx = i;
  });
  return out;
}
