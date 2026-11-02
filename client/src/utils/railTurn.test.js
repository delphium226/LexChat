// P4.25. Run with `npm test` in client/ (Node's own test runner; no dependency).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { railTurn } from './railTurn.js';

const SRC_A = [{ n: 1, title: 'Act A', url: 'https://www.legislation.gov.uk/asp/2001/2' }];
const SRC_C = [{ n: 1, title: 'SSI C', url: 'https://www.legislation.gov.uk/ssi/2008/216' }];

const user = text => ({ role: 'user', content: text });
const answer = (id, sources) => ({ role: 'assistant', id, content: `answer ${id}`, ...(sources ? { sources } : {}) });

// The client before P4.25 (App.jsx's `activeSources` and `latestSourceMsgId`), kept to show the defect.
function before(messages, selectedId) {
  if (selectedId != null) {
    const msg = messages.find(m => m.id === selectedId);
    if (msg?.sources?.length) return msg.sources;
  }
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant' && messages[i].sources?.length) return messages[i].sources;
  }
  return [];
}

test('the defect: before P4.25 an answer with no sources showed the previous answer\'s', () => {
  const msgs = [user('q1'), answer(1, SRC_A), user('q2'), answer(2, [])];
  assert.deepEqual(before(msgs, null), SRC_A);
  // and the completion of answer 1 had pinned the selection to it
  assert.deepEqual(before(msgs, 1), SRC_A);
});

test('a latest answer with no sources owns the rail and shows none', () => {
  for (const empty of [[], undefined, null]) {
    const msgs = [user('q1'), answer(1, SRC_A), user('q2'), answer(2, empty)];
    const r = railTurn(msgs, null, false);
    assert.equal(r.id, 2);
    assert.deepEqual(r.sources, []);
    assert.equal(r.hasTurn, true);
    assert.equal(r.earlierId, 1, 'offers the earlier answer, does not show it');
  }
});

test('selecting an answer with no sources shows none, not a fallback', () => {
  const msgs = [user('q1'), answer(1, SRC_A), user('q2'), answer(2, []), user('q3'), answer(3, SRC_C)];
  const r = railTurn(msgs, 2, false);
  assert.equal(r.id, 2);
  assert.deepEqual(r.sources, []);
  assert.equal(r.earlierId, 1);
});

test('nothing changes for an answer with sources', () => {
  const msgs = [user('q1'), answer(1, SRC_A), user('q2'), answer(2, SRC_C)];
  assert.deepEqual(railTurn(msgs, null, false), { id: 2, sources: SRC_C, hasTurn: true, earlierId: null });
  assert.deepEqual(railTurn(msgs, 1, false), { id: 1, sources: SRC_A, hasTurn: true, earlierId: null });
  // and it matches the old client wherever the answer has sources
  assert.deepEqual(railTurn(msgs, null).sources, before(msgs, null));
  assert.deepEqual(railTurn(msgs, 1).sources, before(msgs, 1));
});

test('a stale selection (not in this transcript) falls to the latest answer', () => {
  const msgs = [user('q1'), answer(1, SRC_A)];
  assert.equal(railTurn(msgs, 99, false).id, 1);
});

test('while a reply streams, the latest finished answer keeps the rail', () => {
  const msgs = [user('q1'), answer(1, SRC_A), user('q2'), { role: 'assistant', content: 'partial…' }];
  assert.deepEqual(railTurn(msgs, null, true).sources, SRC_A);
  // not streaming, an id-less last message (a saved-failed answer, an error text) owns the rail
  const r = railTurn(msgs, null, false);
  assert.equal(r.id, null);
  assert.deepEqual(r.sources, []);
  assert.equal(r.earlierId, 1);
});

test('an unsaved answer that carries sources shows them', () => {
  const msgs = [user('q1'), { role: 'assistant', content: 'a', sources: SRC_C }];
  assert.deepEqual(railTurn(msgs, null, false).sources, SRC_C);
});

test('before the first answer there is no turn', () => {
  assert.deepEqual(railTurn([], null), { id: null, sources: [], hasTurn: false, earlierId: null });
  assert.deepEqual(railTurn([user('q1')], null, true), { id: null, sources: [], hasTurn: false, earlierId: null });
  assert.equal(railTurn(undefined, null).hasTurn, false);
});

test('earlierId skips answers with no id or no sources', () => {
  const msgs = [
    user('q1'), answer(1, SRC_A),
    user('q2'), { role: 'assistant', content: 'unsaved', sources: SRC_C },
    user('q3'), answer(3, []),
    user('q4'), answer(4, []),
  ];
  assert.equal(railTurn(msgs, null).earlierId, 1);
  assert.equal(railTurn(msgs, 3).earlierId, 1);
  assert.equal(railTurn([user('q'), answer(5, [])], null).earlierId, null);
});

test('a user message never owns the rail, even with a matching id', () => {
  const msgs = [{ role: 'user', id: 7, content: 'q', sources: SRC_C }, answer(8, [])];
  const r = railTurn(msgs, 7);
  assert.equal(r.id, 8);
  assert.deepEqual(r.sources, []);
});
