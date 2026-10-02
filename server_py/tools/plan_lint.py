#!/usr/bin/env python
"""Structural lint of the pre-pilot fix plan (FIX_PLAN.md). Free: reads one file.

    python -m tools.plan_lint [--plan PATH] [--only CHECK[,CHECK...]]

Exit 0 when no check reports an ERROR (warnings print but do not fail), 1 otherwise.

**Why a lint and not a re-read.** The plan is a 500 KB hand-edited file that four
agents and an integrator fold into in a day, and its structure decays where no
command reads it: Session 36's probe found 21 rows named in no line of the bucket
index, done marks that disagreed with the ticks, and a cp1252 byte that broke the
file's encoding (`e5c32b3`). `plan_status` reads the ticks and the bucket lines
and is right about both; nothing read the rest. This does, with one function per
check so each can be tested on a synthetic plan:

  shape    every ledger row has exactly three cells (a stray `|`, including one
           inside a code span, splits a cell, and GitHub drops every cell past the
           header's three), a known status box, an id `plan_status` reads, and a
           unique id;
  index    every row is named (as the head of an entry) in exactly one line of the
           "Bucket -> row index": a bucket line, or the `*(no bucket)*` line, which
           IS the allowlist of rows that close no bucket;
  done     an entry carries `**done**` exactly when its row is ticked
           (DONE_MARK_CONVENTION: "every" ticked row is marked);
  depends  every id in a `**Depends on:**` clause is a row; a ticked row that
           depends on an unticked one is a WARNING unless the clause says
           "ticked ahead" (three rows were ticked so by user decision);
  order    the top "Recommended order" line's "N of M rows" and "K of 14 buckets"
           agree with `plan_status` (WARNING: older lines are history);
  bold     every row line, and every other paragraph, has an even number of `**`;
           ODD_LITERALS excuses the one known odd literal by its exact text;
  encoding the file decodes as UTF-8 (ERROR) and has one line ending throughout
           (WARNING).

Parsing is `plan_status`'s own (`_rows`, `_buckets`, `bucket_state`), not a fork:
when the lint and the status disagree about what a row or a closed bucket is, one
of them is wrong, and they must not be able to drift apart quietly.

What it deliberately does NOT do: judge whether a tick is deserved, which bucket
a row belongs in, or anything about the prose. Those are the plan's decisions.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import plan_status as ps  # noqa: E402

ERROR, WARNING = "ERROR", "WARNING"
CHECKS = ("shape", "index", "done", "depends", "order", "bold", "encoding")

# One convention for the index's done marks: "every" ticked row's entry carries
# `**done**` and no other does; "none" means no entry carries one.
DONE_MARK_CONVENTION = "every"

# The file's one known odd `**` literal: a code span quoting a regex in P0.2.
# Excused only on that row's line, by its exact text.
ODD_LITERALS = {"P0.2": "`**Key findings`"}

NO_BUCKET = "*(no bucket)*"

_ROWLIKE = re.compile(r"^\| `\[(.)\]` \|")
_ROW_ID = re.compile(r"^\| `\[.\]` \| \*\*(P\d+\.\d+)\*\* \|")
_ID = re.compile(r"P\d+\.\d+")
_INDEX_HEAD = re.compile(r"^## Bucket .* row index")
_INDEX_LINE = re.compile(r"^\| (B\d+[^|]*?|\*\(no bucket\)\*) \|(.*)\|\s*$")
_ENTRY = re.compile(r"^(P\d+\.\d+)(.*)$", re.S)
_DONE = " **done**"
_ORDER = re.compile(r"^\*\*Recommended order as at [^*]*\*\*.*$", re.M)
_STATUSES = {"x", " ", "~", "-"}


@dataclass(frozen=True)
class Finding:
    level: str
    check: str
    message: str


@dataclass
class Entry:
    raw: str        # the entry exactly as written, no surrounding ", "
    head: str       # the row it names
    refs: list      # row ids mentioned inside its parenthetical
    done: bool      # carries **done**


@dataclass
class IndexLine:
    lineno: int
    key: str        # "B5", or NO_BUCKET
    prefix: str     # everything up to and including the cell's opening "| "
    entries: list
    bad: list       # entries that did not parse


def _row_key(rid: str):
    return [int(x) for x in rid[1:].split(".")]


def _status(text: str) -> dict:
    """row id -> plan_status's word for its box (done/open/wip/dropped)."""
    return {rid: st for _w, st, rid, _t in ps._rows(text)}


def _key_of(label: str) -> str:
    return NO_BUCKET if label == NO_BUCKET else label.split()[0]


# --------------------------------------------------------------------------
# index parsing (shared by checks 2 and 3, and by the fold script)

def split_top_level(cell: str) -> list:
    """Split an index cell on commas outside parentheses."""
    out, depth, cur = [], 0, []
    for ch in cell:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [p.strip() for p in out if p.strip()]


def parse_entry(raw: str):
    """`P3.1 (gloss) **done**` -> Entry, or None when it does not parse."""
    m = _ENTRY.match(raw)
    if not m:
        return None
    head, rest = m.group(1), m.group(2)
    done = rest.endswith(_DONE)
    if done:
        rest = rest[: -len(_DONE)]
    refs = []
    if rest.strip():
        rest = rest.strip()
        if not (rest.startswith("(") and rest.endswith(")")):
            return None
        depth = 0
        for i, ch in enumerate(rest):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i != len(rest) - 1:
                return None   # a second group, or text after the parenthetical
        if depth:
            return None
        refs = _ID.findall(rest)
    return Entry(raw=raw, head=head, refs=refs, done=done)


def parse_index(text: str) -> list:
    """The index's lines, in order. [] when the section is missing."""
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if _INDEX_HEAD.match(l)), None)
    if start is None:
        return []
    out = []
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if l.startswith("## ") or l.strip() == "---":
            break
        m = _INDEX_LINE.match(l)
        if not m:
            continue
        cell = m.group(2)
        entries, bad = [], []
        for raw in split_top_level(cell):
            e = parse_entry(raw)
            (entries.append(e) if e else bad.append(raw))
        prefix = l[: m.start(2)]
        out.append(IndexLine(i + 1, _key_of(m.group(1).strip()), prefix, entries, bad))
    return out


# --------------------------------------------------------------------------
# the checks

def check_encoding(raw: bytes) -> list:
    out = []
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        line = raw[: e.start].count(b"\n") + 1
        out.append(Finding(ERROR, "encoding",
                           f"not UTF-8: byte 0x{raw[e.start]:02x} at offset {e.start} "
                           f"(line {line})"))
    if raw.startswith(b"\xef\xbb\xbf"):
        out.append(Finding(WARNING, "encoding", "starts with a UTF-8 BOM"))
    crlf, lf = raw.count(b"\r\n"), raw.count(b"\n")
    if crlf and crlf != lf:
        out.append(Finding(WARNING, "encoding",
                           f"mixed line endings: {crlf} CRLF of {lf} lines"))
    return out


def _code_span_at(cell: str, pos: int) -> bool:
    return cell[:pos].count("`") % 2 == 1


def check_row_shape(text: str) -> list:
    out, seen = [], {}
    read_by_status = {rid for _w, _s, rid, _t in ps._rows(text)}
    for n, line in enumerate(text.split("\n"), 1):
        m = _ROWLIKE.match(line)
        if not m:
            continue
        idm = _ROW_ID.match(line)
        rid = idm.group(1) if idm else f"line {n}"
        if m.group(1) not in _STATUSES:
            out.append(Finding(ERROR, "shape", f"{rid}: unknown status box `[{m.group(1)}]`"))
        if not idm:
            out.append(Finding(ERROR, "shape", f"line {n}: a ledger row with no readable id"))
        elif rid not in read_by_status:
            out.append(Finding(ERROR, "shape",
                               f"{rid} (line {n}): plan_status does not read this row "
                               "(its title must be bold straight after the id)"))
        if idm:
            seen.setdefault(rid, []).append(n)
        pipes = [p.start() for p in re.finditer(r"(?<!\\)\|", line)]
        closed = line.rstrip().endswith("|")
        cells = len(pipes) - 1 if closed else len(pipes)   # a trailing `|` is optional
        if cells != 3:
            body_start = pipes[2] + 1 if len(pipes) > 2 else 0
            extra = pipes[3:-1] if closed else pipes[3:]
            in_code = sum(_code_span_at(line[body_start:], p - body_start) for p in extra)
            out.append(Finding(
                ERROR, "shape",
                f"{rid} (line {n}): {cells} cells, expected 3; "
                f"{len(extra)} stray `|` ({in_code} inside a code span, "
                f"{len(extra) - in_code} outside); GitHub drops every cell past the third"))
    for rid, ns in seen.items():
        if len(ns) > 1:
            out.append(Finding(ERROR, "shape", f"{rid}: id used by {len(ns)} rows (lines "
                               + ", ".join(map(str, ns)) + ")"))
    return out


def check_index_coverage(text: str) -> list:
    index = parse_index(text)
    if not index:
        return [Finding(ERROR, "index", "no '## Bucket -> row index' section with lines")]
    out = []
    rows = _status(text)
    named, referenced = {}, {}
    for il in index:
        for raw in il.bad:
            out.append(Finding(ERROR, "index",
                               f"{il.key} (line {il.lineno}): entry does not parse: "
                               f"{raw[:60]!r}"))
        heads = {e.head for e in il.entries}
        for e in il.entries:
            named.setdefault(e.head, []).append(il.key)
            for r in e.refs:
                if r == e.head:
                    continue
                referenced.setdefault(r, []).append((il.key, e.head))
                if il.key != NO_BUCKET and r not in heads:
                    out.append(Finding(
                        WARNING, "index",
                        f"{il.key}: {r} is mentioned inside {e.head}'s parenthetical and "
                        f"is not an entry of the line, but plan_status counts it as a "
                        f"closure dependency of {il.key}"))
    for rid in sorted(set(named) | set(referenced), key=_row_key):
        if rid not in rows:
            out.append(Finding(ERROR, "index", f"{rid}: named in the index but no such row"))
    for rid in sorted(rows, key=_row_key):
        where = named.get(rid, [])
        if len(where) > 1:
            out.append(Finding(ERROR, "index",
                               f"{rid}: named in {len(where)} index lines ({', '.join(where)})"))
        elif not where:
            refs = [f"{h} on {k}" for k, h in referenced.get(rid, [])]
            if refs:
                out.append(Finding(WARNING, "index",
                                   f"{rid}: not named; only mentioned inside "
                                   + "; ".join(refs)))
            else:
                out.append(Finding(ERROR, "index",
                                   f"{rid}: in no bucket line and not in the "
                                   f"{NO_BUCKET} line"))
    return out


def check_done_marks(text: str, convention: str = None) -> list:
    convention = convention or DONE_MARK_CONVENTION
    rows = _status(text)
    out = []
    for il in parse_index(text):
        for e in il.entries:
            if e.head not in rows:
                continue          # reported by the index check
            ticked = rows[e.head] == "done"
            want = ticked if convention == "every" else False
            if e.done and not want:
                why = (f"is {rows[e.head]}" if convention == "every"
                       else "is marked, and the convention is that none are")
                out.append(Finding(ERROR, "done",
                                   f"{il.key}: {e.head} carries **done** but {why}"))
            elif want and not e.done:
                out.append(Finding(ERROR, "done",
                                   f"{il.key}: {e.head} is ticked but carries no **done**"))
    return out


def depends_clauses(line: str) -> list:
    """The text of each `**Depends on:**` clause in a row line, cut at the cell's
    end, at "Related:", and at the first bold run that is not a bold row id."""
    out = []
    for m in re.finditer(r"\*\*Depends on:\*\*", line):
        clause = line[m.end():].split("|", 1)[0]
        clause = clause.split("Related:", 1)[0]
        clause = re.sub(r"\*\*(P\d+\.\d+)\*\*", r"\1", clause)
        clause = clause.split("**", 1)[0]
        out.append(clause)
    return out


def dependency_ids(clause: str, row_ids) -> tuple:
    """(ids, unknown) named by a clause; `P1.1–P1.4` and `P2.*` expand over rows."""
    ids, unknown = [], []
    for m in re.finditer(r"P(\d+)\.(\d+)\s*[–-]\s*P(\d+)\.(\d+)", clause):
        a, b = (int(m.group(1)), int(m.group(2))), (int(m.group(3)), int(m.group(4)))
        ids += [r for r in row_ids if a <= tuple(_row_key(r)) <= b]
    clause_rest = re.sub(r"P\d+\.\d+\s*[–-]\s*P\d+\.\d+", " ", clause)
    for m in re.finditer(r"P(\d+)\.\*", clause_rest):
        wave = int(m.group(1))
        ids += [r for r in row_ids if _row_key(r)[0] == wave]
    for rid in _ID.findall(clause_rest):
        (ids if rid in row_ids else unknown).append(rid)
    return ids, unknown


def check_dependencies(text: str) -> list:
    rows = _status(text)
    out = []
    for line in text.split("\n"):
        idm = _ROW_ID.match(line)
        if not idm:
            continue
        rid = idm.group(1)
        clauses = depends_clauses(line)
        if not clauses:
            out.append(Finding(WARNING, "depends", f"{rid}: no **Depends on:** clause"))
            continue
        for clause in clauses:
            ids, unknown = dependency_ids(clause, list(rows))
            for u in unknown:
                out.append(Finding(ERROR, "depends", f"{rid}: depends on {u}, which is no row"))
            if rid in ids:
                out.append(Finding(ERROR, "depends", f"{rid}: depends on itself"))
            if rows.get(rid) != "done" or "ticked ahead" in clause.lower():
                continue
            open_deps = [d for d in dict.fromkeys(ids) if rows.get(d) != "done"]
            if open_deps:
                out.append(Finding(
                    WARNING, "depends",
                    f"{rid} is ticked but depends on " + ", ".join(
                        f"{d} ({rows[d]})" for d in open_deps)
                    + "; say why in the clause (\"ticked ahead of ...\")"))
    return out


def check_order_counts(text: str) -> list:
    m = _ORDER.search(text)
    if not m:
        return [Finding(WARNING, "order", "no 'Recommended order as at' line")]
    top = m.group(0)
    status = _status(text)
    done, total = sum(s == "done" for s in status.values()), len(status)
    buckets = ps._buckets(text)
    closed = sum(ps.bucket_state(deps, status) == "closed" for _l, deps in buckets.values())
    out = []
    head = top[: top.index(":**") + 1] if ":**" in top else top[:60]
    for pat, want, what in ((r"(\d+) of (\d+) rows", (done, total), "rows"),
                            (r"(\d+) of (\d+) buckets", (closed, len(buckets)), "buckets")):
        found = [(int(a), int(b)) for a, b in re.findall(pat, top)]
        if not found:
            out.append(Finding(WARNING, "order", f"top line ({head}) states no '{what}' count"))
        for got in found:
            if got != want:
                out.append(Finding(WARNING, "order",
                                   f"top line ({head}) says {got[0]} of {got[1]} {what}; "
                                   f"plan_status says {want[0]} of {want[1]}"))
    return out


def _excused(rid, line: str) -> str:
    lit = ODD_LITERALS.get(rid)
    return line.replace(lit, "", 1) if lit else line


def check_bold_parity(text: str) -> list:
    out = []
    lines = text.split("\n")
    block, fenced = [], False

    def flush():
        if not block:
            return
        if all(l.startswith("|") for _n, l in block):
            for n, l in block:
                idm = _ROW_ID.match(l)
                rid = idm.group(1) if idm else None
                c = _excused(rid, l).count("**")
                if c % 2:
                    out.append(Finding(ERROR, "bold",
                                       f"{rid or 'table line'} (line {n}): {c} `**`, odd"))
        else:
            c = sum(l.count("**") for _n, l in block)
            if c % 2:
                out.append(Finding(ERROR, "bold",
                                   f"paragraph at lines {block[0][0]}-{block[-1][0]}: "
                                   f"{c} `**`, odd"))
        block.clear()

    for n, l in enumerate(lines, 1):
        if l.startswith("```"):
            flush()
            fenced = not fenced
            continue
        if fenced:
            continue
        if not l.strip():
            flush()
        else:
            block.append((n, l))
    flush()
    return out


def lint(raw: bytes, only=None) -> list:
    """Every finding on the plan's bytes, in check order."""
    only = set(only or CHECKS)
    out = check_encoding(raw) if "encoding" in only else []
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    for name, fn in (("shape", check_row_shape), ("index", check_index_coverage),
                     ("done", check_done_marks), ("depends", check_dependencies),
                     ("order", check_order_counts), ("bold", check_bold_parity)):
        if name in only:
            out += fn(text)
    return out


def main(argv=None) -> int:
    ps._utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", type=Path, default=ps.FIX_PLAN)
    ap.add_argument("--only", default=",".join(CHECKS),
                    help="comma-separated checks: " + ", ".join(CHECKS))
    a = ap.parse_args(argv)
    only = [c.strip() for c in a.only.split(",") if c.strip()]
    bad = [c for c in only if c not in CHECKS]
    if bad:
        ap.error(f"unknown check(s): {', '.join(bad)}")
    raw = a.plan.read_bytes()
    findings = lint(raw, only)
    status = _status(raw.decode("utf-8", errors="replace").replace("\r\n", "\n"))
    print(f"plan_lint - {a.plan}")
    print(f"  {len(status)} rows, {sum(s == 'done' for s in status.values())} ticked; "
          f"checks: {', '.join(only)}")
    for f in findings:
        print(f"  {f.level:7} [{f.check}] {f.message}")
    errors = [f for f in findings if f.level == ERROR]
    warnings = [f for f in findings if f.level == WARNING]
    per = {c: sum(f.check == c for f in errors) for c in only}
    print(f"  {len(errors)} error(s), {len(warnings)} warning(s); errors by check: "
          + ", ".join(f"{c} {n}" for c, n in per.items()))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
