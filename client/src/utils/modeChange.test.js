// P4.9. Run with `npm test` in client/ (Node's own test runner; no dependency).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { modeChangeMarkers, modeChangeParts } from './modeChange.js';
import { CHAT_MODE_LABELS, RESEARCH_TYPE_LABELS, RESEARCH_TYPE_OPTIONS } from '../constants/research.js';

const user = text => ({ role: 'user', content: text });
const answer = (id, research_mode, chat_mode) => ({
  role: 'assistant',
  id,
  content: `answer ${id}`,
  ...(research_mode !== undefined ? { research_mode } : {}),
  ...(chat_mode !== undefined ? { chat_mode } : {}),
});
const texts = (markers, at) => (markers.get(at) || []).map(p => p.text);

test('a changed research type renders one marker, above the question it was first used for', () => {
  const msgs = [
    user('q1'),
    answer(1, 'legislation_only', 'conversational'),
    user('q2'),
    answer(2, 'legislation_and_case_law', 'conversational'),
  ];
  const m = modeChangeMarkers(msgs);
  assert.equal(m.size, 1);
  assert.deepEqual(texts(m, 2), ['Research type changed to Legislation & case law']);
});

test('a changed chat mode renders one marker', () => {
  const msgs = [user('q1'), answer(1, 'legislation_only', 'conversational'), user('q2'), answer(2, 'legislation_only', 'research')];
  const m = modeChangeMarkers(msgs);
  assert.equal(m.size, 1);
  assert.deepEqual(texts(m, 2), ['Mode changed to Research']);
});

test('both controls changed between two answers: still one marker, research type first', () => {
  const msgs = [user('q1'), answer(1, 'case_law_only', 'conversational'), user('q2'), answer(2, 'legislation_only', 'research')];
  const m = modeChangeMarkers(msgs);
  assert.equal(m.size, 1);
  assert.deepEqual(texts(m, 2), ['Research type changed to Legislation only', 'Mode changed to Research']);
});

test('equal stamps render none', () => {
  const msgs = [
    user('q1'),
    answer(1, 'legislation_only', 'conversational'),
    user('q2'),
    answer(2, 'legislation_only', 'conversational'),
    user('q3'),
    answer(3, 'legislation_only', 'conversational'),
  ];
  assert.equal(modeChangeMarkers(msgs).size, 0);
});

test('unstamped (pre-column) rows render none, on either side of a stamped one', () => {
  for (const [a, b] of [
    [answer(1), answer(2, 'legislation_and_case_law', 'research')],
    [answer(1, 'legislation_only', 'conversational'), answer(2)],
    [answer(1, null, null), answer(2, 'legislation_and_case_law', 'research')],
    [answer(1, '', ''), answer(2, 'legislation_and_case_law', 'research')],
    [answer(1), answer(2)],
  ]) {
    assert.equal(modeChangeMarkers([user('q1'), a, user('q2'), b]).size, 0);
  }
});

test('one key stamped on both sides is compared; the other, missing on one side, is not', () => {
  const msgs = [user('q1'), answer(1, 'legislation_only', undefined), user('q2'), answer(2, 'case_law_only', 'research')];
  assert.deepEqual(texts(modeChangeMarkers(msgs), 2), ['Research type changed to Case law only']);
});

test('an unstamped answer between two stamped ones breaks the comparison, as the backend reads it', () => {
  // The backend compares with the LAST assistant message only (`previous_modes`).
  const msgs = [
    user('q1'),
    answer(1, 'legislation_only', 'conversational'),
    user('q2'),
    { role: 'assistant', content: 'Error: Request Timeout' },
    user('q3'),
    answer(3, 'legislation_and_case_law', 'conversational'),
  ];
  assert.equal(modeChangeMarkers(msgs).size, 0);
});

test('Deep Research back to Conversational is silent; into Deep Research is shown', () => {
  const msgs = [
    user('q1'),
    answer(1, 'legislation_only', 'conversational'),
    user('q2'),
    answer(2, 'legislation_only', 'deep_research'),
    user('q3'),
    answer(3, 'legislation_only', 'conversational'),
  ];
  const m = modeChangeMarkers(msgs);
  assert.equal(m.size, 1);
  assert.deepEqual(texts(m, 2), ['Mode changed to Deep Research']);
  // Deep Research to Research is the user's own switch, so it is shown.
  assert.deepEqual(
    modeChangeParts(answer(1, 'legislation_only', 'deep_research'), answer(2, 'legislation_only', 'research')).map(p => p.text),
    ['Mode changed to Research']
  );
});

test('a planner clarification and the Deep Research answer after it are one mode: no marker between them', () => {
  const msgs = [
    user('q1'),
    answer(1, 'legislation_only', 'conversational'),
    user('q2'),
    answer(2, 'legislation_only', 'deep_research'), // the planner's question
    user('Scotland'),
    answer(3, 'legislation_only', 'deep_research'), // the report
  ];
  const m = modeChangeMarkers(msgs);
  assert.deepEqual([...m.keys()], [2]);
});

test('no user message between two answers: the marker sits above the later answer', () => {
  const msgs = [user('q1'), answer(1, 'legislation_only', 'research'), answer(2, 'case_law_only', 'research')];
  assert.deepEqual([...modeChangeMarkers(msgs).keys()], [2]);
});

test('the marker sits above the FIRST user message after the earlier answer', () => {
  const msgs = [
    user('q1'),
    answer(1, 'legislation_only', 'research'),
    user('q2'),
    { role: 'tool', content: '{}' },
    user('q2 again'),
    answer(2, 'case_law_only', 'research'),
  ];
  assert.deepEqual([...modeChangeMarkers(msgs).keys()], [2]);
});

test('a still-streaming draft (no stamps yet) renders no marker until its result arrives', () => {
  const msgs = [user('q1'), answer(1, 'legislation_only', 'research'), user('q2'), { role: 'assistant', content: 'partial' }];
  assert.equal(modeChangeMarkers(msgs).size, 0);
});

test('a value with no UI label is not shown', () => {
  assert.deepEqual(modeChangeParts(answer(1, 'legislation_only', 'research'), answer(2, 'drafting', 'mystery')), []);
  assert.deepEqual(
    modeChangeParts(answer(1, 'legislation_only', 'research'), answer(2, 'parliamentary_records', 'research')),
    []
  );
});

test('bad input never throws', () => {
  for (const bad of [undefined, null, 'x', {}, [null, undefined, 3]]) {
    assert.equal(modeChangeMarkers(bad).size, 0);
  }
});

// The control names are the UI's, verbatim, and agree with the server's.
function pyDict(source, name) {
  const m = source.match(new RegExp(`^${name} = \\{([\\s\\S]*?)^\\}`, 'm'));
  assert.ok(m, `${name} not found in mode_change.py`);
  return Object.fromEntries([...m[1].matchAll(/"([a-z_]+)":\s*"([^"]+)"/g)].map(x => [x[1], x[2]]));
}

test("the client's labels match the server's (mode_change.py) for every option the UI offers", () => {
  const py = readFileSync(new URL('../../../server_py/src/utils/mode_change.py', import.meta.url), 'utf-8');
  const serverResearch = pyDict(py, 'RESEARCH_MODE_LABELS');
  const serverChat = pyDict(py, 'CHAT_MODE_LABELS');
  for (const { value, label } of RESEARCH_TYPE_OPTIONS) assert.equal(serverResearch[value], label, value);
  assert.deepEqual(CHAT_MODE_LABELS, serverChat);
  assert.deepEqual(Object.keys(RESEARCH_TYPE_LABELS), ['legislation_only', 'case_law_only', 'legislation_and_case_law']);
  // And the server names the two controls as the UI does.
  assert.match(py, /RESEARCH_TYPE_CONTROL = \(\s*"the Filters button above the message box \(Research filters > Research type\)"/);
  assert.match(py, /CHAT_MODE_CONTROL = "the Mode menu in the sidebar"/);
});
