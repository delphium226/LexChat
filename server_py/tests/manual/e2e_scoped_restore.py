"""End-to-end exercise of the D14 Phase 4/5 scoped restore.

NOT a pytest module - it needs a live cluster with CREATEDB, the PostgreSQL
client binaries, and a real run of deployment/backup_databases.ps1. See the
README beside this file for what each stage proves; stage 8b is the reason it
exists.

Runs against a scratch database (lexchat_e2e), dropped and recreated each time.
It NEVER touches `lexchat`. Drives the real code paths: developer.clear_data()
for the loss and services.backup_restore.run_restore() for the recovery.

Usage:  python server_py/tests/manual/e2e_scoped_restore.py
"""

import asyncio
import json
import os
import subprocess
import sys

E2E_DB = "lexchat_e2e"
BACKUP_ROOT = r"C:\Temp\BackupsDev"
PG_BIN = r"C:\Program Files\PostgreSQL\18\bin"
# Resolved from this file so the script does not care where the repo lives.
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# MUST precede any src import: config.Settings is instantiated at module import.
os.environ["DATABASE_URL"] = f"postgresql://lexuser:lexpassword@localhost:5432/{E2E_DB}"
os.environ["BACKUP_ROOT"] = BACKUP_ROOT
os.environ["PG_BIN"] = PG_BIN
os.environ["LOG_LEVEL"] = "WARNING"

sys.path.insert(0, os.path.join(REPO, "server_py"))

ALL_SCOPES = ["chats", "performance", "feedback", "activity", "health", "cache"]

FAILURES = []
CHECKS = 0


def check(label, actual, expected):
    global CHECKS
    CHECKS += 1
    ok = actual == expected
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got {actual!r}, expected {expected!r}")
    if not ok:
        FAILURES.append(f"{label}: got {actual!r}, expected {expected!r}")


def note(msg):
    print(f"  ..   {msg}")


def psql(db, sql, allow_fail=False):
    env = dict(os.environ, PGPASSWORD="lexpassword")
    r = subprocess.run(
        [os.path.join(PG_BIN, "psql.exe"), "-U", "lexuser", "-h", "localhost",
         "-d", db, "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True, text=True, env=env,
    )
    if r.returncode != 0 and not allow_fail:
        raise RuntimeError(f"psql failed on {db}: {r.stderr.strip()}")
    return r.stdout.strip()


def recreate_scratch_db():
    psql("postgres", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                     f"WHERE datname='{E2E_DB}' AND pid<>pg_backend_pid()", allow_fail=True)
    psql("postgres", f'DROP DATABASE IF EXISTS "{E2E_DB}"')
    psql("postgres", f'CREATE DATABASE "{E2E_DB}" OWNER lexuser')


def run_backup():
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(REPO, "deployment", "backup_databases.ps1"),
         "-BackupRoot", BACKUP_ROOT, "-SkipRetention"],
        capture_output=True, text=True, cwd=REPO,
    )
    if r.returncode != 0:
        raise RuntimeError(f"backup_databases.ps1 failed:\n{r.stdout}\n{r.stderr}")
    run_id = None
    for line in r.stdout.splitlines():
        if "Run directory:" in line:
            run_id = os.path.basename(line.split("Run directory:")[1].strip())
    if not run_id:
        raise RuntimeError("Could not parse the run directory from the backup output.")
    return run_id


COUNT_SQL = """
SELECT
  (SELECT count(*) FROM chats)                                        AS chats,
  (SELECT count(*) FROM messages)                                     AS messages,
  (SELECT count(*) FROM documents)                                    AS documents,
  (SELECT count(*) FROM messages
    WHERE rating IS NOT NULL OR feedback_comment IS NOT NULL)         AS rated,
  (SELECT count(*) FROM product_feedback)                             AS product_feedback,
  (SELECT count(*) FROM session_feedback)                             AS session_feedback,
  (SELECT count(*) FROM session_feedback WHERE chat_id IS NOT NULL)   AS sf_linked,
  (SELECT count(*) FROM request_timings)                              AS request_timings,
  (SELECT count(*) FROM activity_log WHERE event_type <> 'RESTORE')   AS activity_log,
  (SELECT count(*) FROM service_health_logs)                          AS health,
  (SELECT count(*) FROM local_prompt_cache)                           AS cache,
  (SELECT count(*) FROM matter_notes)                                 AS matter_notes,
  (SELECT count(*) FROM matter_notes WHERE message_id IS NOT NULL)    AS notes_linked,
  (SELECT count(*) FROM matters)                                      AS matters,
  (SELECT count(*) FROM users)                                        AS users
"""


def counts():
    keys = ["chats", "messages", "documents", "rated", "product_feedback",
            "session_feedback", "sf_linked", "request_timings", "activity_log",
            "health", "cache", "matter_notes", "notes_linked", "matters", "users"]
    row = psql(E2E_DB, COUNT_SQL).split("|")
    return dict(zip(keys, (int(v) for v in row)))


async def seed():
    """Seed via raw SQL so ids are deterministic and json/float columns are exercised."""
    from src.database import init_db
    await init_db()          # real schema creation + additive migrations

    psql(E2E_DB, """
INSERT INTO users (id, username, password_hash, email, role, dark_mode, research_mode, chat_mode, created_at)
VALUES (900,'e2e_alice','x','alice@e2e.test','user',false,'legislation_only','research',NOW()),
       (901,'e2e_bob','x','bob@e2e.test','user',false,'legislation_only','research',NOW()),
       (902,'e2e_doomed','x','doomed@e2e.test','user',false,'legislation_only','research',NOW());

INSERT INTO matters (id, user_id, title, description, status, created_at, updated_at)
VALUES (700,900,'Compulsory purchase','CPO research','open',NOW(),NOW()),
       (701,901,'Housing standards',NULL,'open',NOW(),NOW());

INSERT INTO chats (id, user_id, matter_id, title, model, provider, created_at)
VALUES (500,900,700,'Acquiring authority procedure','google/gemini-2.0-flash','openrouter',NOW()),
       (501,900,NULL,'Compensation basis','google/gemini-2.0-flash','openrouter',NOW()),
       (502,901,701,'HMO licensing','google/gemini-2.0-flash','openrouter',NOW()),
       (503,901,NULL,'Unlinked thread',NULL,NULL,NOW()),
       (504,902,NULL,'Chat of a user about to vanish',NULL,NULL,NOW());

INSERT INTO messages (id, chat_id, role, content, model, provider, rating, feedback_comment,
                      cost_usd, sources, research_plan, created_at)
VALUES
 (300,500,'user','What is the CPO confirmation procedure?',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NOW()),
 (301,500,'assistant','Under the Acquisition of Land Act 1981 ...','google/gemini-2.0-flash','openrouter',
   5,'Exactly what I needed',0.0182,
   '[{"title":"Acquisition of Land Act 1981","url":"https://lex.example/ala1981"}]'::json,
   NULL,NOW()),
 (302,501,'user','How is compensation assessed?',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NOW()),
 (303,501,'assistant','The Land Compensation Act 1961 ...','google/gemini-2.0-flash','openrouter',
   4,NULL,0.0091,'[{"title":"Land Compensation Act 1961","url":"https://lex.example/lca1961"}]'::json,
   '{"scope_note":"Two-step","steps":[{"id":1,"title":"Statute","detail":"Find the Act"}]}'::json,NOW()),
 (304,502,'user','HMO licensing thresholds?',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NOW()),
 (305,502,'assistant','Part 5 of the Housing (Scotland) Act 2006 ...','google/gemini-2.0-flash','openrouter',
   NULL,'Useful but missed the 2011 amendment',0.0074,NULL,NULL,NOW()),
 (306,503,'user','Unrated question',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NOW()),
 (307,503,'assistant','Unrated answer','google/gemini-2.0-flash','openrouter',NULL,NULL,0.0031,NULL,NULL,NOW()),
 (308,504,'user','Question from the doomed user',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NOW()),
 (309,504,'assistant','Answer to the doomed user','google/gemini-2.0-flash','openrouter',3,NULL,0.0012,NULL,NULL,NOW());

INSERT INTO documents (id, chat_id, user_id, filename, content_text, size_bytes, created_at)
VALUES (200,500,900,'cpo-notes.txt','Notes on the CPO process',24,NOW()),
       (201,502,901,'hmo.txt','HMO licensing notes',19,NOW()),
       (202,504,902,'doomed.txt','Belongs to the doomed user',26,NOW());

INSERT INTO matter_notes (id, matter_id, content, message_id, created_at)
VALUES (100,700,'Key authority for confirmation',301,NOW()),
       (101,700,'Compensation basis note',303,NOW()),
       (102,701,'HMO threshold note',305,NOW()),
       (103,701,'Standalone note with no message link',NULL,NOW());

INSERT INTO product_feedback (id, user_id, message, time_saved_hours, research_success,
                              confidence, usability, verification_hours, created_at)
VALUES (60,900,'Saved me an afternoon',3.5,'yes',4,5,0.5,NOW()),
       (61,901,'Good but slow on long Acts',1.25,'partially',3,4,1.0,NOW());

INSERT INTO session_feedback (id, user_id, chat_id, message_count, manual_time_hours,
                              time_saved_hours, session_continuity, found_right_law,
                              right_jurisdiction, references_accurate, refers_incorrectly,
                              confidence, ease_of_use, other_comments, filters, created_at)
VALUES (80,900,500,2,4.0,3.0,'one_go','yes','yes','yes','no',5,5,'Excellent',
        '{"jurisdiction":"England","chat_mode":"research"}'::json,NOW()),
       (81,901,502,2,2.0,1.5,'not_one_go','partially','yes','partially','no',3,4,'Mixed',
        '{"jurisdiction":"Scotland"}'::json,NOW()),
       (82,901,NULL,0,1.0,0.5,'one_go','no','no','no','yes',2,3,'Unlinked feedback',NULL,NOW());

INSERT INTO activity_log (id, event_type, username, description, created_at)
VALUES (20,'LOGIN','e2e_alice','Signed in',NOW()),
       (21,'LOGIN','e2e_bob','Signed in',NOW()),
       (22,'EFFICIENCY','e2e_alice','Fan-out: 6 retrievals for 2 sources',NOW());

INSERT INTO service_health_logs (id, service_name, is_healthy, error_message, latency_ms, checked_at)
VALUES (10,'lex_api',true,NULL,142,NOW()),
       (11,'lex_api',false,'HTTP 503 from lex.lab.i.ai.gov.uk',NULL,NOW()),
       (12,'openrouter',true,NULL,88,NOW());

INSERT INTO local_prompt_cache (id, content_hash, query_hash, query_text, summary,
                                summarise_model, doc_name, chars_in, hit_count, created_at)
VALUES (1,'aa11','bb22','what is an acquiring authority','An acquiring authority is ...',
        'google/gemini-2.0-flash','ALA 1981 s.1',18422,3,NOW()),
       (2,'cc33','dd44','hmo licensing threshold','Part 5 requires a licence where ...',
        'google/gemini-2.0-flash','H(S)A 2006 Part 5',9310,1,NOW());
""")

    # request_timings has ~36 NOT NULL columns whose defaults are SQLAlchemy-side,
    # not server-side, so a raw INSERT has to supply every one. Built from
    # information_schema so this does not rot the next time a metric is added.
    required = psql(E2E_DB, """
SELECT string_agg(column_name, ',' ORDER BY ordinal_position)
FROM information_schema.columns
WHERE table_schema='public' AND table_name='request_timings'
  AND is_nullable='NO' AND column_default IS NULL AND column_name <> 'created_at'
""").split(",")
    interesting = [
        {"id": 40, "request_id": "req0000000000a1", "total_ms": 64210.5, "llm_calls": 7,
         "llm_total_ms": 61233.25, "total_cost_usd": 0.1824, "manager_delegations": 1,
         "worker_tool_calls": 6, "chat_mode": "research"},
        {"id": 41, "request_id": "req0000000000a2", "total_ms": 31005.25, "llm_calls": 4,
         "llm_total_ms": 29110.75, "total_cost_usd": 0.0912, "manager_delegations": 1,
         "worker_tool_calls": 3, "chat_mode": "research"},
        {"id": 42, "request_id": "req0000000000a3", "total_ms": 122400.0, "llm_calls": 12,
         "llm_total_ms": 118990.5, "total_cost_usd": 0.4411, "manager_delegations": 3,
         "worker_tool_calls": 11, "chat_mode": "deep_research"},
    ]
    cols = ["id"] + required + ["research_mode", "chat_mode", "provider", "model",
                                "source", "created_at"]
    cols = list(dict.fromkeys(cols))
    rows = []
    for spec in interesting:
        vals = []
        for c in cols:
            if c == "created_at":
                vals.append("NOW()")
            elif c in spec:
                v = spec[c]
                vals.append(f"'{v}'" if isinstance(v, str) else str(v))
            elif c in ("research_mode",):
                vals.append("'legislation_only'")
            elif c == "provider":
                vals.append("'openrouter'")
            elif c == "model":
                vals.append("'google/gemini-2.0-flash'")
            elif c == "source":
                vals.append("'app'")
            elif c == "request_id":
                vals.append("'req000000000000'")
            else:
                vals.append("0")
        rows.append("(" + ",".join(vals) + ")")
    psql(E2E_DB, f"INSERT INTO request_timings ({','.join(cols)}) VALUES {','.join(rows)}")


async def do_clear(scopes):
    """The REAL Danger Zone code path."""
    from src.database import async_session_maker
    from src.routers.developer import ClearDataRequest, clear_data

    async with async_session_maker() as session:
        return await clear_data(ClearDataRequest(scopes=scopes, confirm="DELETE"), session)


async def do_restore(run_id, scopes, dry_run):
    from src.database import async_session_maker
    from src.services import backup_restore

    async with async_session_maker() as session:
        return await backup_restore.run_restore(session, run_id, scopes, dry_run=dry_run)


def show_components(result, header):
    print(f"  --- {header} ---")
    for c in result["components"]:
        flag = "" if c["available"] else "  (UNAVAILABLE)"
        n = c["would_apply"] if result["dry_run"] else c["applied"]
        print(f"      {c['scope']:<12} {c['label']:<28} {c['operation']:<7} "
              f"staging={c['staging_rows']:<6} live={c['live_rows']:<6} "
              f"{'would' if result['dry_run'] else 'did'}={n}{flag}")
        for msg in c["notes"]:
            print(f"          - {msg}")


async def main():
    print("\n=== STAGE 1: build and seed the scratch database ===")
    recreate_scratch_db()
    await seed()
    seeded = counts()
    print(f"  seeded: {json.dumps(seeded)}")
    check("seeded rated messages", seeded["rated"], 4)
    check("seeded matter_notes with message links", seeded["notes_linked"], 3)

    print("\n=== STAGE 2: real nightly backup run ===")
    run_id = run_backup()
    print(f"  backup run: {run_id}")
    dump = os.path.join(BACKUP_ROOT, run_id, f"{E2E_DB}.dump")
    check("dump exists for the scratch database", os.path.isfile(dump), True)

    print("\n=== STAGE 3: pilot reset - clear ALL SIX scopes via the real Danger Zone ===")
    cleared = await do_clear(ALL_SCOPES)
    print(f"  clear_data reported: {cleared['deleted']}")
    after_clear = counts()
    print(f"  after clear: {json.dumps(after_clear)}")
    check("chats gone", after_clear["chats"], 0)
    check("messages gone", after_clear["messages"], 0)
    check("documents gone (cascade)", after_clear["documents"], 0)
    check("product_feedback gone", after_clear["product_feedback"], 0)
    check("session_feedback gone", after_clear["session_feedback"], 0)
    check("ratings gone", after_clear["rated"], 0)
    check("matter_notes SURVIVE the clear", after_clear["matter_notes"], 4)
    check("but their message links are SEVERED (4f)", after_clear["notes_linked"], 0)
    check("request_timings gone", after_clear["request_timings"], 0)
    check("activity_log gone", after_clear["activity_log"], 0)
    check("service health gone", after_clear["health"], 0)
    check("local prompt cache gone", after_clear["cache"], 0)
    check("matters untouched", after_clear["matters"], 2)
    check("users untouched", after_clear["users"], seeded["users"])

    print("\n=== STAGE 4: preflight (dry run) ===")
    pre = await do_restore(run_id, ALL_SCOPES, dry_run=True)
    show_components(pre, "preflight")
    check("preflight changed nothing", counts()["chats"], 0)
    check("preflight total > 0", pre["total_rows"] > 0, True)

    print("\n=== STAGE 5: the real scoped restore ===")
    res = await do_restore(run_id, ALL_SCOPES, dry_run=False)
    show_components(res, "restore")
    print(f"  safety dump: {res['safety_dump']}")
    print(f"  sequences reset: {res['sequences_reset']}")
    restored = counts()
    print(f"  after restore: {json.dumps(restored)}")

    check("chats restored", restored["chats"], seeded["chats"])
    check("messages restored", restored["messages"], seeded["messages"])
    check("documents restored", restored["documents"], seeded["documents"])
    check("product_feedback restored", restored["product_feedback"], seeded["product_feedback"])
    check("session_feedback restored", restored["session_feedback"], seeded["session_feedback"])
    check("session_feedback chat links restored", restored["sf_linked"], seeded["sf_linked"])
    check(">>> MESSAGE RATINGS RESTORED (4b)", restored["rated"], seeded["rated"])
    check(">>> matter_note message links repaired (4f)", restored["notes_linked"], seeded["notes_linked"])
    check("request_timings restored", restored["request_timings"], seeded["request_timings"])
    check("activity_log restored", restored["activity_log"], seeded["activity_log"])
    check("service health restored", restored["health"], seeded["health"])
    check("local prompt cache NOT restored (excluded by design)", restored["cache"], 0)

    print("\n  --- rating values, not just the count ---")
    ratings = psql(E2E_DB, "SELECT id||':'||coalesce(rating::text,'-')||':'||"
                           "coalesce(feedback_comment,'-') FROM messages "
                           "WHERE rating IS NOT NULL OR feedback_comment IS NOT NULL ORDER BY id")
    for line in ratings.splitlines():
        note(line)
    check("message 301 rating value", psql(E2E_DB, "SELECT rating FROM messages WHERE id=301"), "5")
    check("message 301 comment value",
          psql(E2E_DB, "SELECT feedback_comment FROM messages WHERE id=301"),
          "Exactly what I needed")
    check("message 305 comment-only rating restored",
          psql(E2E_DB, "SELECT coalesce(rating::text,'NULL')||'/'||feedback_comment "
                       "FROM messages WHERE id=305"),
          "NULL/Useful but missed the 2011 amendment")

    print("\n  --- json columns survived the text round trip ---")
    check("messages.sources json intact",
          psql(E2E_DB, "SELECT sources->0->>'title' FROM messages WHERE id=301"),
          "Acquisition of Land Act 1981")
    check("messages.research_plan json intact",
          psql(E2E_DB, "SELECT research_plan->'steps'->0->>'title' FROM messages WHERE id=303"),
          "Statute")
    check("session_feedback.filters json intact",
          psql(E2E_DB, "SELECT filters->>'jurisdiction' FROM session_feedback WHERE id=80"),
          "England")
    check("float cost_usd exact",
          psql(E2E_DB, "SELECT cost_usd = 0.0182 FROM messages WHERE id=301"), "t")
    check("request_timings float exact after round trip",
          psql(E2E_DB, "SELECT total_ms = 64210.5 FROM request_timings WHERE id=40"), "t")
    check("request_timings cost float exact",
          psql(E2E_DB, "SELECT total_cost_usd = 0.1824 FROM request_timings WHERE id=40"), "t")
    check("boolean round trip (service_health_logs.is_healthy)",
          psql(E2E_DB, "SELECT count(*) FROM service_health_logs WHERE is_healthy = false"), "1")

    print("\n=== STAGE 6: sequences (4d) - the next real INSERT must not collide ===")
    for table in ("chats", "messages", "documents", "product_feedback", "session_feedback",
                  "request_timings", "activity_log", "service_health_logs"):
        maxid = psql(E2E_DB, f"SELECT coalesce(max(id),0) FROM {table}")
        nextval = psql(E2E_DB, f"SELECT nextval(pg_get_serial_sequence('{table}','id'))")
        ok = int(nextval) > int(maxid)
        print(f"  [{'PASS' if ok else 'FAIL'}] {table}: max(id)={maxid}, nextval={nextval}")
        if not ok:
            FAILURES.append(f"sequence for {table} not advanced past max(id)")

    new_chat = psql(E2E_DB, "INSERT INTO chats (user_id, title, created_at) "
                            "VALUES (900,'post-restore chat',NOW()) RETURNING id"
                    ).splitlines()[0].strip()
    note(f"a genuine post-restore INSERT succeeded with id {new_chat}")
    psql(E2E_DB, f"DELETE FROM chats WHERE id={new_chat}")

    print("\n=== STAGE 7: re-run the same restore (4c: additive and re-runnable) ===")
    again = await do_restore(run_id, ALL_SCOPES, dry_run=False)
    show_components(again, "second restore")
    check("second run inserted nothing new", sum(c["applied"] for c in again["components"]), 0)
    check("counts unchanged after re-run", counts()["messages"], seeded["messages"])

    print("\n=== STAGE 8: the `cache` scope is unrestorable by design ===")
    cache_pre = await do_restore(run_id, ["cache"], dry_run=True)
    show_components(cache_pre, "cache preflight")
    cache_comp = cache_pre["components"][0]
    check("cache component reported unavailable", cache_comp["available"], False)
    check("cache note mentions the exclusion",
          "excluded from every backup by design" in " ".join(cache_comp["notes"]), True)

    print("\n=== STAGE 8b: the EXACT 4b trap - `feedback` scope on its own ===")
    note("With `chats` also selected, messages are DELETEd and re-INSERTed carrying their")
    note("rating columns, so ratings return via the INSERT and the trap is masked.")
    note("Clearing ONLY `feedback` leaves the message rows in place - which is the case")
    note("where INSERT ... ON CONFLICT (id) DO NOTHING restores nothing yet reports success.")
    fb_cleared = await do_clear(["feedback"])
    print(f"  clear_data reported: {fb_cleared['deleted']}")
    fb_after = counts()
    check("message rows SURVIVED the feedback clear", fb_after["messages"], seeded["messages"])
    check("but every rating is gone", fb_after["rated"], 0)
    check("product_feedback gone", fb_after["product_feedback"], 0)
    check("session_feedback gone", fb_after["session_feedback"], 0)

    fb_pre = await do_restore(run_id, ["feedback"], dry_run=True)
    show_components(fb_pre, "feedback-only preflight")
    ratings_pre = next(c for c in fb_pre["components"] if c["key"] == "feedback.messages")
    check("preflight: all 4 ratings would be restored", ratings_pre["would_apply"], 4)
    check("preflight: none already present", ratings_pre["already_present"], 0)

    fb_res = await do_restore(run_id, ["feedback"], dry_run=False)
    show_components(fb_res, "feedback-only restore")
    ratings_did = next(c for c in fb_res["components"] if c["key"] == "feedback.messages")
    check(">>> the UPDATE component restored 4 ratings", ratings_did["applied"], 4)
    fb_restored = counts()
    check(">>> RATINGS BACK after a feedback-only restore", fb_restored["rated"], 4)
    check("product_feedback back", fb_restored["product_feedback"], 2)
    check("session_feedback back", fb_restored["session_feedback"], 3)
    check("no messages duplicated", fb_restored["messages"], seeded["messages"])
    check("rating + comment on message 301",
          psql(E2E_DB, "SELECT rating||'|'||feedback_comment FROM messages WHERE id=301"),
          "5|Exactly what I needed")
    check("rating-only message 303", psql(
        E2E_DB, "SELECT rating||'|'||coalesce(feedback_comment,'NULL') FROM messages WHERE id=303"),
          "4|NULL")
    check("comment-only message 305", psql(
        E2E_DB, "SELECT coalesce(rating::text,'NULL')||'|'||feedback_comment FROM messages WHERE id=305"),
          "NULL|Useful but missed the 2011 amendment")
    note("an INSERT ... ON CONFLICT (id) DO NOTHING would have conflicted on all 10")
    note("surviving message rows and restored 0 of these 4 ratings.")

    fb_again = await do_restore(run_id, ["feedback"], dry_run=False)
    ratings_again = next(c for c in fb_again["components"] if c["key"] == "feedback.messages")
    check("re-running feedback-only reports 0 applied (no phantom updates)",
          ratings_again["applied"], 0)

    print("\n=== STAGE 9: stale FK parents (4e) ===")
    await do_clear(ALL_SCOPES)
    psql(E2E_DB, "DELETE FROM users WHERE id=902")
    psql(E2E_DB, "DELETE FROM matters WHERE id=701")
    note("deleted user 902 (owns chat 504) and matter 701 (referenced by chat 502)")
    fk = await do_restore(run_id, ALL_SCOPES, dry_run=False)
    show_components(fk, "restore with missing parents")
    chats_comp = next(c for c in fk["components"] if c["key"] == "chats.chats")
    check("chat of the deleted user skipped", chats_comp["skipped_missing_parent"], 1)
    check("chat of the deleted matter kept with matter_id nulled",
          chats_comp["nulled_references"], 1)
    check("4 of 5 chats restored", chats_comp["applied"], 4)
    check("orphaned chat 504 absent",
          psql(E2E_DB, "SELECT count(*) FROM chats WHERE id=504"), "0")
    check("chat 502 present with NULL matter_id",
          psql(E2E_DB, "SELECT count(*) FROM chats WHERE id=502 AND matter_id IS NULL"), "1")
    msg_comp = next(c for c in fk["components"] if c["key"] == "chats.messages")
    check("messages of the skipped chat skipped too", msg_comp["skipped_missing_parent"], 2)
    # 4 seeded ratings minus message 309, which sits on chat 504 - skipped because
    # its owning user was deleted by hand above.
    check("ratings restored except the one on the skipped chat",
          counts()["rated"], 3)

    print("\n=== STAGE 10: activity_log RESTORE audit rows ===")
    audit = psql(E2E_DB, "SELECT count(*) FROM activity_log WHERE event_type='RESTORE'")
    note(f"RESTORE rows written by run_restore's caller: {audit} "
         "(0 is expected here - the endpoint writes them, not the service)")

    print("\n" + "=" * 70)
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} FAILURE(S) out of {CHECKS} checks")
        for f in FAILURES:
            print(f"  - {f}")
    else:
        print(f"RESULT: all {CHECKS} checks passed")
    print("=" * 70)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
