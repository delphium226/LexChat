// P4.27: the line under the Jurisdiction filter saying what it keeps.
//
// The filter had labels only. What it does (`_matches_jurisdiction`,
// server_py/src/agent/tools/lex.py, run on legislation searches only):
//   - a stated extent decides: a row is kept where its extent includes the
//     chosen nation, or the United Kingdom (and Great Britain for Great
//     Britain's nations), the "applies in" reading decided at P1.1;
//   - a row whose extent the index does not state (57.8% of stored rows) is
//     kept, unless its identifier marks it as made for another part of the UK
//     (an `nisr/` instrument under Scotland, for example);
//   - "UK-wide only" keeps a row only where its stated extent is the United
//     Kingdom, so it drops every row with no stated extent;
//   - case law is not filtered by it.
// `jurisdictionNote.test.js` checks those facts against lex.py.
// Pure, so it is tested without a browser.

const PLACE = {
  england_and_wales: 'England or Wales',
  scotland: 'Scotland',
  northern_ireland: 'Northern Ireland',
  wales: 'Wales',
};

const CASE_LAW = 'Case law is not filtered.';

export function jurisdictionFilterNote(jurisdiction, researchMode) {
  if (!jurisdiction) return null;
  if (researchMode === 'case_law_only') {
    return 'Case law is not filtered by jurisdiction: this filter narrows legislation searches only.';
  }
  if (jurisdiction === 'uk_wide') {
    return (
      'Legislation searches keep only legislation whose stated extent is the whole UK. Legislation whose extent ' +
      'the index does not state is left out, so UK-wide law that does not say so is missed. ' +
      CASE_LAW
    );
  }
  const place = PLACE[jurisdiction];
  if (!place) return null;
  return (
    `Legislation searches keep legislation that applies in ${place}, UK-wide legislation included. ` +
    'Legislation whose extent the index does not state is kept too, unless it was made for another part of ' +
    'the UK. ' +
    CASE_LAW
  );
}
