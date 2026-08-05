# Drafting bot — session log

Append-only, newest last. One entry per session. Read `BUILD_PLAN.md` first, then this file
for what actually happened.

The **Surprises / deviations** line is the one that matters — it is where a cold-starting
session learns that reality diverged from the plan.

## Entry template

```markdown
## Session N — <date> — <ledger row>
**Done:** …
**Surprises / deviations from BUILD_PLAN:** …
**State of the branch:** <commit sha>, tests <green|N failing>
**Next action:** <the single next thing>
```

---
