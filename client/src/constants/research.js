// Shared research-filter option lists. Used by App.jsx (context chips + label
// derivation) and ResearchFiltersModal (the filter popover). Static — kept at
// module scope so they aren't rebuilt on every render.

export const RECORD_TYPE_OPTIONS = [
  { value: null, label: 'All records' },
  { value: 'debates', label: 'Chamber debates' },
  { value: 'written_answers', label: 'Written answers' },
  { value: 'committee', label: 'Committee transcripts' },
];

export const JURISDICTION_OPTIONS = [
  { value: null, label: 'All jurisdictions' },
  { value: 'england_and_wales', label: 'England & Wales' },
  { value: 'scotland', label: 'Scotland' },
  { value: 'northern_ireland', label: 'Northern Ireland' },
  { value: 'wales', label: 'Wales' },
  { value: 'uk_wide', label: 'UK-wide only' },
];

export const JURISDICTION_SHORT = {
  england_and_wales: 'E&W',
  scotland: 'SCO',
  northern_ireland: 'NI',
  wales: 'WAL',
  uk_wide: 'UK',
};

export const LEGISLATION_TYPE_OPTIONS = [
  { value: null, label: 'All types' },
  { value: 'primary', label: 'Acts (primary)' },
  { value: 'secondary', label: 'SIs & Rules (secondary)' },
  { value: 'draft', label: 'Draft instruments' },
];

export const COURT_GROUPS = [
  {
    group: 'UK-wide',
    courts: [
      { value: 'uksc', label: 'UK Supreme Court' },
      { value: 'ukpc', label: 'Privy Council' },
    ],
  },
  {
    group: 'Court of Appeal',
    courts: [
      { value: 'ewca/civ', label: 'Civil Division' },
      { value: 'ewca/crim', label: 'Criminal Division' },
    ],
  },
  {
    group: 'High Court',
    courts: [
      { value: 'ewhc/admin', label: 'Administrative Court' },
      { value: 'ewhc/qb', label: "King's Bench" },
      { value: 'ewhc/ch', label: 'Chancery' },
      { value: 'ewhc/fam', label: 'Family' },
      { value: 'ewhc/comm', label: 'Commercial' },
      { value: 'ewhc/pat', label: 'Patents' },
      { value: 'ewhc/tcc', label: 'Technology & Construction' },
    ],
  },
  {
    group: 'Tribunals',
    courts: [
      { value: 'ukut', label: 'Upper Tribunal' },
      { value: 'ukut/iac', label: 'Immigration & Asylum' },
      { value: 'ukut/lc', label: 'Lands Chamber' },
      { value: 'eat', label: 'Employment Appeal' },
    ],
  },
];
