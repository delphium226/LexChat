// P4.25: which answer the Sources rail belongs to, and what it shows.
//
// Before this, the rail showed the selected answer's sources only when it had
// some, and otherwise fell back to the latest earlier answer that did, with
// that earlier answer's Sources button highlighted. An answer with no source
// of its own (a report that vouched for none, P4.3; a follow-up answered
// without research) therefore showed another answer's sources as if they were
// its own: 353 of 2,295 stored answered turns.
//
// Now the rail always belongs to one answer: the one selected with its
// Sources button, else the latest answer. Its sources are that answer's, and
// an answer with none says so (`hasTurn` true, `sources` empty), offering the
// latest earlier answer that has sources (`earlierId`) for the user to open.
// Pure, so it is tested without a browser (`railTurn.test.js`).

// The reply still streaming in: the last message, an assistant draft with no
// id yet. It has no sources until its result arrives, so it never owns the
// rail; the latest finished answer keeps it meanwhile.
const isStreamingDraft = (messages, i, streaming) =>
  streaming && i === messages.length - 1 && messages[i].role === 'assistant' && messages[i].id == null;

// The latest assistant message before index `before` that has sources and an
// id (an id is what its Sources button selects).
const earlierWithSources = (messages, before) => {
  for (let i = before - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === 'assistant' && m.id != null && m.sources?.length) return m.id;
  }
  return null;
};

/**
 * @param {Array} messages     the visible transcript
 * @param {*} selectedId       the answer whose Sources button was last pressed (or set on completion)
 * @param {boolean} streaming  the visible chat is streaming a reply
 * @returns {{id: *, sources: Array, hasTurn: boolean, earlierId: *}}
 *   id        the answer the rail belongs to (null when there is none, or it has no id)
 *   sources   that answer's sources, [] when it has none
 *   hasTurn   an answer owns the rail (false only before the first answer)
 *   earlierId when that answer has no sources: the latest earlier answer that has, else null
 */
export function railTurn(messages, selectedId, streaming = false) {
  const list = Array.isArray(messages) ? messages : [];
  let index = -1;
  if (selectedId != null) {
    index = list.findIndex(m => m.role === 'assistant' && m.id === selectedId);
  }
  if (index < 0) {
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].role !== 'assistant' || isStreamingDraft(list, i, streaming)) continue;
      index = i;
      break;
    }
  }
  if (index < 0) return { id: null, sources: [], hasTurn: false, earlierId: null };
  const msg = list[index];
  const sources = msg.sources?.length ? msg.sources : [];
  return {
    id: msg.id ?? null,
    sources,
    hasTurn: true,
    earlierId: sources.length ? null : earlierWithSources(list, index),
  };
}
