"""P4.14: stored answers with more than one `*Search scope:` line, rebuilt through
the answer seam's footer steps before and after P4.14.

The model sometimes copies the previous turn's scope line back. Until P4.14 the
seam removed such an echo only at the very end, just before the real footer
went on, so an echo followed by P1.6's "No provision-level URL" note (appended
after the model's text) survived and the lawyer read two scope lines. P4.14
strips the echo while it is still the end of the model's text.

A stored answer does not carry the model's own text, so this rebuilds it:

    stored = strip(body [+ "\\n\\n" + note]) + footer

where `footer` is the code-appended trailing scope line and `note` is P1.6's
footnote when it ends what precedes the footer (read as appended by code, which
is how `enforce_provision_links` puts it there). Then

    before P4.14: strip(body [+ note]) + footer
    after  P4.14: strip(strip(body) [+ note]) + footer

using the product's own `strip_answer_footer`. Every answer the two differ on is
listed, so each edit can be read (`--text` prints the text ahead of the footer:
it quotes answers, keep the output out of the repo). Informational: exits 0.

    python -m tools.footer_echo --dir <replay dir> [--all-dirs] [--export] [--text]
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.citation_links import PROVISION_FOOTNOTE  # noqa: E402
from src.utils.search_scope import strip_answer_footer  # noqa: E402
from tools import replay_report as rr  # noqa: E402

_MARK = "*Search scope:"
_LAST_LINE = re.compile(r"\n*^(\*Search scope:[^\n]*\*)[ \t]*\s*\Z", re.M)


def split_answer(answer: str) -> tuple:
    """(body, had_note, footer) of a stored answer; see the module docstring."""
    m = _LAST_LINE.search(answer or "")
    if m:
        footer, pre = "\n\n" + m.group(1), answer[:m.start()].rstrip()
    else:
        footer, pre = "", answer or ""
    had_note = pre.endswith(PROVISION_FOOTNOTE)
    body = pre[: -len(PROVISION_FOOTNOTE)].rstrip() if had_note else pre
    return body, had_note, footer


def rebuild(answer: str, p414: bool) -> str:
    """The stored answer through the seam's footer steps, before or after P4.14."""
    body, had_note, footer = split_answer(answer)
    if p414:
        body = strip_answer_footer(body)
    if had_note:
        body = body.rstrip() + "\n\n" + PROVISION_FOOTNOTE
    return strip_answer_footer(body) + footer


def answer_rows(dirs: list, export: bool) -> list:
    rows = []
    for d in dirs:
        for doc in rr.load_runs(d):
            for i, t in enumerate(doc.get("turns") or [], 1):
                a = t.get("answer") or ""
                if a.strip():
                    rows.append({"dir": d.name, "session": str(doc.get("session_id")),
                                 "rep": doc.get("rep"), "turn": i,
                                 "mode": t.get("chat_mode") or "?", "answer": a})
    if export:
        rs = rr._replay_set_module()
        if rs is None:
            print("  export not read: replay_set unavailable")
        else:
            for r in rr._opener_export_rows(rs):
                rows.append({**r, "dir": "export"})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True, help="a replay directory")
    ap.add_argument("--all-dirs", action="store_true",
                    help="every directory beside --dir")
    ap.add_argument("--export", action="store_true",
                    help="also the pre-pilot's own answers (transcript export)")
    ap.add_argument("--text", action="store_true",
                    help="print the text ahead of the footer for each changed answer "
                         "(quotes answers: keep out of the repo)")
    ap.add_argument("--chars", type=int, default=700)
    args = ap.parse_args(argv)

    base = Path(args.dir)
    dirs = ([d for d in sorted(base.parent.iterdir()) if d.is_dir()]
            if args.all_dirs else [base])
    rows = answer_rows(dirs, args.export)
    stored, before, after = Counter(), Counter(), Counter()
    changed = []
    for r in rows:
        a = r["answer"]
        b, f = rebuild(a, p414=False), rebuild(a, p414=True)
        stored[r["dir"]] += a.count(_MARK) > 1
        before[r["dir"]] += b.count(_MARK) > 1
        after[r["dir"]] += f.count(_MARK) > 1
        if b != f:
            changed.append((r, b, f))

    def _nz(c):
        return {k: v for k, v in c.items() if v}

    print(f"P4.14 over {len(rows)} answers in {len({r['dir'] for r in rows})} group(s)")
    print(f"  more than one scope line, as stored:      {sum(stored.values())} {_nz(stored)}")
    print(f"  ... rebuilt through the seam before P4.14: {sum(before.values())} {_nz(before)}")
    print(f"  ... rebuilt through the seam after P4.14:  {sum(after.values())} {_nz(after)}")
    print(f"  answers P4.14 changes: {len(changed)}")
    for r, b, f in changed:
        print(f"    {r['dir']:<20} {r['session']} r{r['rep']} t{r['turn']:<3} "
              f"{r['mode']:<14} scope lines {b.count(_MARK)} -> {f.count(_MARK)}, "
              f"chars {len(b)} -> {len(f)}")
        if args.text:
            cut = "\n\n" + _MARK
            for label, s in (("before", b), ("after", f)):
                head = s[: s.rfind(cut)] if cut in s else s
                print(f"      {label}:\n        "
                      + head[-args.chars:].replace("\n", "\n        "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
