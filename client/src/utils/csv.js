// CSV export for the Admin Portal tabs.
//
// Generated in the browser from the rows a tab already holds, rather than by a
// second server-side query. The feedback endpoints do real work before they
// return — /api/feedback/session excludes the operator's own login and treats a
// resubmitted form as a correction rather than a second response — and an
// export built from its own SQL would be a second place those rules have to
// agree. Serialising what is on screen means the CSV always reconciles with the
// figures above it.

// Excel reads a bare UTF-8 file as the system codepage, mangling anything typed
// outside ASCII (curly quotes, £, é) — which, in free-text feedback, is most of
// it. The BOM is what tells it otherwise. Built from its code point rather than
// written as a literal — a literal BOM is invisible in an editor and is exactly
// the sort of character a well-meaning save or lint pass strips out.
const BOM = String.fromCharCode(0xfeff);

// Excel and LibreOffice evaluate a cell beginning =, +, - or @ as a formula, so
// text starting with one is prefixed with a quote. Tab and CR are included
// because both are also treated as leading separators.
//
// Applied to STRINGS ONLY: numbers go through untouched, or a negative hours
// value would arrive in the spreadsheet as the text "'-1.5" and drop out of
// every average computed over the column.
const FORMULA_START = /^[=+\-@\t\r]/;

const cell = value => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  let text = String(value);
  if (FORMULA_START.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

/**
 * Serialise rows to RFC4180 CSV.
 *
 * @param {Array<object>} rows
 * @param {Array<{label: string, value: (row: object) => unknown}>} columns
 */
export function toCsv(rows, columns) {
  const lines = [columns.map(c => cell(c.label)).join(',')];
  for (const row of rows) {
    lines.push(columns.map(c => cell(c.value(row))).join(','));
  }
  return BOM + lines.join('\r\n');
}

/** Trigger a browser download of `csv` as `filename`. */
export function downloadCsv(filename, csv) {
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** `2026-08-13`, for filenames — locale-independent and sorts correctly. */
export const csvDateStamp = () => new Date().toISOString().slice(0, 10);
