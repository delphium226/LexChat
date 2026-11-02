// P4.27. Run with `npm test` in client/ (Node's own test runner; no dependency).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { jurisdictionFilterNote } from './jurisdictionNote.js';
import { JURISDICTION_OPTIONS } from '../constants/research.js';

const SERVER_SRC = fileURLToPath(new URL('../../../server_py/src/', import.meta.url));
const LEX = readFileSync(join(SERVER_SRC, 'agent/tools/lex.py'), 'utf-8');

test('no filter, no line', () => {
  assert.equal(jurisdictionFilterNote(null, 'legislation_only'), null);
  assert.equal(jurisdictionFilterNote(undefined, 'legislation_and_case_law'), null);
  assert.equal(jurisdictionFilterNote('', 'legislation_only'), null);
});

test('every nation filter: applies in, UK-wide included, unstated extent kept, case law not filtered', () => {
  const places = { england_and_wales: 'England or Wales', scotland: 'Scotland', northern_ireland: 'Northern Ireland', wales: 'Wales' };
  for (const [value, place] of Object.entries(places)) {
    for (const mode of ['legislation_only', 'legislation_and_case_law', undefined]) {
      const note = jurisdictionFilterNote(value, mode);
      assert.equal(
        note,
        `Legislation searches keep legislation that applies in ${place}, UK-wide legislation included. ` +
          'Legislation whose extent the index does not state is kept too, unless it was made for another part of the UK. ' +
          'Case law is not filtered.'
      );
    }
  }
});

test('UK-wide only: unstated extent left out', () => {
  assert.equal(
    jurisdictionFilterNote('uk_wide', 'legislation_only'),
    'Legislation searches keep only legislation whose stated extent is the whole UK. Legislation whose extent the ' +
      'index does not state is left out, so UK-wide law that does not say so is missed. Case law is not filtered.'
  );
});

test('case law only: the filter narrows nothing that is searched', () => {
  for (const { value } of JURISDICTION_OPTIONS.filter(o => o.value)) {
    assert.equal(
      jurisdictionFilterNote(value, 'case_law_only'),
      'Case law is not filtered by jurisdiction: this filter narrows legislation searches only.'
    );
  }
});

test('an unknown value says nothing rather than something wrong', () => {
  assert.equal(jurisdictionFilterNote('isle_of_man', 'legislation_only'), null);
});

test('every option the dialog offers has a line', () => {
  for (const { value } of JURISDICTION_OPTIONS.filter(o => o.value)) {
    assert.ok(jurisdictionFilterNote(value, 'legislation_only'), value);
  }
});

// What the line says, checked against the code that does it (lex.py).
function accepts() {
  const m = LEX.match(/^_JURISDICTION_ACCEPTS = \{([\s\S]*?)^\}/m);
  assert.ok(m, '_JURISDICTION_ACCEPTS not found in lex.py');
  return Object.fromEntries(
    [...m[1].matchAll(/"([a-z_]+)":\s*\{([^}]*)\}/g)].map(x => [x[1], new Set([...x[2].matchAll(/"([A-Z]+)"/g)].map(y => y[1]))])
  );
}

test("the dialog's options are the filter's values", () => {
  const values = JURISDICTION_OPTIONS.filter(o => o.value).map(o => o.value).sort();
  assert.deepEqual(values, Object.keys(accepts()).sort());
});

test('UK-wide legislation is kept under every nation filter, and UK-wide only keeps nothing else', () => {
  const a = accepts();
  for (const nation of ['england_and_wales', 'scotland', 'northern_ireland', 'wales']) {
    assert.ok(a[nation].has('UK'), nation);
  }
  assert.deepEqual([...a.uk_wide], ['UK']);
});

test('an unstated extent is dropped only under UK-wide only, or for another part of the UK by its identifier', () => {
  const body = LEX.slice(LEX.indexOf('def _matches_jurisdiction('), LEX.indexOf('def _short_legislation_id('));
  assert.match(body, /if jurisdiction == "uk_wide":\s*\n\s*return False/);
  assert.match(body, /if owner is None:\s*\n\s*return True/);
  const owners = LEX.match(/^_ID_PREFIX_JURISDICTION = \{([\s\S]*?)^\}/m)[1];
  const named = new Set([...owners.matchAll(/:\s*"([a-z_]+)"/g)].map(x => x[1]));
  assert.deepEqual([...named].sort(), ['northern_ireland', 'scotland', 'wales']);
});

test('case law is not filtered: the filter runs only in the legislation search and the definitions search', () => {
  const callers = [];
  const walk = dir => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) walk(p);
      else if (name.endsWith('.py') && /_matches_jurisdiction\(/.test(readFileSync(p, 'utf-8'))) {
        callers.push(p.slice(SERVER_SRC.length).replace(/\\/g, '/'));
      }
    }
  };
  walk(SERVER_SRC);
  assert.deepEqual(callers.sort(), ['agent/tools/executor.py', 'agent/tools/lex.py', 'utils/definitions.py']);
  const exec = readFileSync(join(SERVER_SRC, 'agent/tools/executor.py'), 'utf-8');
  for (const name of ['caselaw', 'scts']) {
    const src = readFileSync(join(SERVER_SRC, `agent/tools/${name}.py`), 'utf-8');
    assert.doesNotMatch(src, /_matches_jurisdiction|_jurisdiction"/, name);
  }
  // The executor reads the filter in two branches: search_legislation and the definitions tool.
  assert.equal((exec.match(/cfg\.get\("_jurisdiction"\)/g) || []).length, 2);
});
