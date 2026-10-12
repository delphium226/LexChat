import Modal from './ui/Modal';

// Reference modal describing the data sources the bot actually queries. The
// same client serves three bots with entirely disjoint sources, so the body is
// selected per-bot rather than shared — only the bot name is interpolated.

// --- Legislation bot: LEX + legislation.gov.uk records + Find Case Law (+ SCTS) ---
// Rewritten 2026-10-12 (FIX_PLAN P4.27's data-sources half, and what P3.5, P3.21,
// P3.31, P3.33, P3.38 and P3.20 added). It describes what the assistant actually
// searches; every limit stated here is one the answers themselves disclose.
function LegislationSources({ botName, scottishJudgments }) {
  return (
    <>
      {/* Legislation */}
      <section>
        <h3 className="text-base font-bold text-ink-900 mb-2">Legislation: the LEX index of UK legislation</h3>
        <p>
          {botName} searches LEX, a search service run by the Government's AI incubator (i.AI) over the legislation
          published on legislation.gov.uk by The National Archives. Through it, {botName} finds Acts and statutory
          instruments, searches inside them for particular provisions, and reads their text, schedules included.
        </p>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">What it covers</h4>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>Primary legislation:</strong> Acts of the UK Parliament, Acts of the Scottish Parliament, Acts and
            Measures of Senedd Cymru, and Acts of the Northern Ireland Assembly.
          </li>
          <li>
            <strong>Secondary legislation:</strong> UK statutory instruments, Scottish statutory instruments and Welsh
            statutory instruments.
          </li>
          <li>
            <strong>Retained (assimilated) EU law</strong> that became part of UK law after Brexit.
          </li>
        </ul>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Records read from legislation.gov.uk</h4>
        <p className="mb-2">
          Alongside the text, {botName} reads legislation.gov.uk's own records, through the same service:
        </p>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>The record of changes:</strong> which later legislation amended, brought into force, repealed or
            revoked which provision, and the date a provision was brought into force where legislation.gov.uk records
            one.
          </li>
          <li>
            <strong>What an instrument was made under:</strong> a record of what each statutory instrument's own
            opening words say it was made under, for Scottish statutory instruments made from 1999 and UK statutory
            instruments made from 1987 (Welsh statutory instruments and Northern Ireland Orders in Council included).
            It answers questions such as "which regulations were made under section 95?", and says which of those
            instruments legislation.gov.uk records as revoked, with the date that was checked.
          </li>
          <li>
            <strong>Instruments missing from the index:</strong> where an instrument named by its number is not held,{' '}
            {botName} reads its text from legislation.gov.uk where it can, and says so.
          </li>
        </ul>
      </section>

      <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
        <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">Important limitations</h4>
        <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
          <li>
            <strong>The index is incomplete.</strong> Most secondary legislation made in the current year is not yet
            held, and some older Acts are missing. When something is not found, {botName} says what it searched; a
            gap in the index is not proof that the legislation does not exist.
          </li>
          <li>
            <strong>Which version of the text.</strong> The text held is either the version as made or enacted, or a
            revised version that legislation.gov.uk updates as amendments are made. Revisions can lag months, or for
            obscure legislation years, behind the amending legislation.
          </li>
          <li>
            <strong>Whether something is in force.</strong> Neither version of the text says whether a provision is in
            force today. {botName} states only what the record of changes shows, with its date; "no revocation
            recorded" does not mean in force, and the record itself can lag. Check the current position before relying
            on it.
          </li>
          <li>
            <strong>Older instruments.</strong> Statutory instruments made before 1987 are mostly published only as
            scanned images and are not in the record of what instruments were made under.
          </li>
        </ul>
      </section>

      {/* Case law */}
      <div className="border-t border-ink-200 pt-6">
        <h3 className="text-base font-bold text-ink-900 mb-2">Case law: The National Archives' Find Case Law</h3>
        <p>
          {botName} searches Find Case Law, the official, government-backed collection of court judgments and tribunal
          decisions published by The National Archives, and reads a judgment's full text. Search results come back
          most relevant first.
        </p>
      </div>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Courts and tribunals covered</h4>
        <div className="space-y-3 pl-2">
          <div>
            <p className="font-medium text-ink-800">UK-wide appellate courts:</p>
            <ul className="list-disc list-inside space-y-1 pl-4">
              <li>The UK Supreme Court, including appeals from Scotland</li>
              <li>The Judicial Committee of the Privy Council</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-ink-800">England &amp; Wales higher courts:</p>
            <ul className="list-disc list-inside space-y-1 pl-4">
              <li>Court of Appeal (Civil and Criminal Divisions)</li>
              <li>High Court (King's Bench, Chancery and Family Divisions)</li>
              <li>Courts Martial Appeal Court</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-ink-800">UK tribunals:</p>
            <ul className="list-disc list-inside space-y-1 pl-4">
              <li>Upper Tribunal (Administrative Appeals, Immigration and Asylum, Lands, and Tax and Chancery Chambers)</li>
              <li>Employment Appeal Tribunal</li>
            </ul>
          </div>
        </div>
      </section>

      {scottishJudgments && (
        <>
          <div className="border-t border-ink-200 pt-6">
            <h3 className="text-base font-bold text-ink-900 mb-2">
              Scottish case law: the Scottish Courts and Tribunals Service
            </h3>
            <p>
              For Scottish judgments, {botName} also searches the judgments published by the Scottish Courts and
              Tribunals Service, and reads a judgment's full text. Both sets of results are searched together, so a
              question of Scots law is answered from Scottish decisions where they bear on it.
            </p>
          </div>
          <section>
            <h4 className="font-semibold text-ink-900 mb-2">Courts and tribunals covered</h4>
            <ul className="list-disc list-inside space-y-1 pl-2">
              <li>Court of Session (Inner and Outer House)</li>
              <li>High Court of Justiciary</li>
              <li>Sheriff Appeal Court</li>
              <li>Sheriff courts (published decisions only)</li>
              <li>Scottish tribunals</li>
            </ul>
            <p className="mt-2">Coverage runs from 1998.</p>
          </section>
        </>
      )}

      <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
        <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">Important limitations</h4>
        <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
          {scottishJudgments ? (
            <li>
              <strong>Scottish judgments:</strong> only decisions the Scottish Courts and Tribunals Service publishes
              are searched. Most sheriff court decisions are not published, and judgments from before 1998 are not
              covered.
            </li>
          ) : (
            <li>
              <strong>Scotland and Northern Ireland:</strong> the domestic courts of Scotland (for example the Court of
              Session and the High Court of Justiciary) and of Northern Ireland are not covered, except where a case
              was appealed to the UK Supreme Court.
            </li>
          )}
          <li>
            <strong>Lower courts:</strong> judgments of the Crown Court, County Courts, magistrates' courts and the
            Family Court are generally not published, and so are not available.
          </li>
          <li>
            <strong>First-tier tribunals:</strong> decisions of lower tribunals, such as the Employment Tribunal and
            the First-tier Tribunal, are not included.
          </li>
          <li>
            <strong>Older judgments:</strong> coverage of older cases is incomplete, and some leading older cases are
            not in the collection at all.
          </li>
          <li>
            <strong>A search can miss a judgment:</strong> a case that does not appear in the results may still exist.
          </li>
        </ul>
      </section>
    </>
  );
}

// --- Holyrood bot: SP Official Report + TheyWorkForYou + SP Bills API -------
function HolyroodSources({ botName }) {
  return (
    <>
      <section>
        <h3 className="text-base font-bold text-ink-900 mb-2">
          Source Overview: The Scottish Parliament Official Report
        </h3>
        <p>
          {botName} draws on the Official Report published by the Scottish Parliament at parliament.scot — the
          verbatim, substantially-as-spoken record of proceedings at Holyrood. Transcripts are indexed into a local
          full-text database ahead of time, so a search returns the speeches themselves rather than a link to a page;{' '}
          {botName} then retrieves the full text of the specific agenda item it needs.
        </p>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Proceedings Covered</h4>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>Plenary (chamber) debates:</strong> Meetings of the Parliament, broken down into individual agenda
            items — debates, ministerial statements, question times, and stage proceedings on bills.
          </li>
          <li>
            <strong>Committee transcripts:</strong> Meetings of Holyrood's committees, again by agenda item, including
            evidence sessions and stage 1 / stage 2 bill scrutiny.
          </li>
          <li>
            <strong>Written answers:</strong> Available in excerpt form via TheyWorkForYou (see below).
          </li>
        </ul>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Speaker Attribution</h4>
        <p>
          Each contribution is stored against the member who made it, so {botName} can attribute a statement to a
          named MSP or minister. This matters for purposive interpretation — for example, retrieving a minister's own
          statement of a provision's purpose during the passage of a bill.
        </p>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Supporting Sources</h4>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>TheyWorkForYou</strong> (theyworkforyou.com) — an independent mirror of parliamentary records,
            used as a breadth fallback for plenary material outside the indexed range, for written answers, and for
            MSP biographical detail (party, constituency, roles). Results are excerpt-level rather than full text.
          </li>
          <li>
            <strong>Scottish Parliament Bills API</strong> (data.parliament.scot) — bill titles, current stage, and
            passage status for bills before the Scottish Parliament.
          </li>
        </ul>
      </section>

      <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
        <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">Important Limitations</h4>
        <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
          <li>
            <strong>Session coverage:</strong> Full-text indexing is comprehensive for Session 6 onwards (2021 to
            present). Earlier sessions are only partially indexed, and questions about them may fall back to
            excerpt-level results from TheyWorkForYou or return nothing at all.
          </li>
          <li>
            <strong>Publication lag:</strong> The Official Report for a sitting is not published immediately.
            Proceedings from the last few days may not yet be retrievable, and the index is refreshed daily rather
            than in real time.
          </li>
          <li>
            <strong>Scotland only:</strong> {botName} does not cover UK Parliament (Westminster) proceedings, the
            Senedd, or the Northern Ireland Assembly.
          </li>
          <li>
            <strong>Not the statute book:</strong> The Official Report records what was <em>said</em> in Parliament,
            which is not the same as what the law <em>is</em>. For the text of an Act or SSI, and for its current
            in-force status, consult the legislation assistant.
          </li>
        </ul>
      </section>
    </>
  );
}

// --- Westminster bot: Hansard API + Members API + Bills API -----------------
function WestminsterSources({ botName }) {
  return (
    <>
      <section>
        <h3 className="text-base font-bold text-ink-900 mb-2">Source Overview: UK Parliament Hansard</h3>
        <p>
          {botName} connects to the official Hansard API operated by the UK Parliament (published under the Open
          Parliament Licence v3.0). Hansard is the edited verbatim report of proceedings at Westminster — a
          substantially-as-spoken record of what was said, by whom, and when. Searches are relevance-ranked and run
          against Hansard directly, and {botName} can then retrieve the full contributions for a specific debate.
        </p>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Proceedings Covered</h4>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>House of Commons:</strong> Chamber debates, ministerial statements, and oral questions.
          </li>
          <li>
            <strong>House of Lords:</strong> Chamber debates, statements, and questions.
          </li>
          <li>
            <strong>Westminster Hall:</strong> Parallel-chamber debates, including e-petition debates.
          </li>
          <li>
            <strong>Public Bill Committees:</strong> Line-by-line committee-stage scrutiny of bills.
          </li>
        </ul>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Supporting Sources</h4>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>UK Parliament Members API</strong> (members-api.parliament.uk) — name, party, constituency, House,
            and current-membership status for MPs and Members of the House of Lords.
          </li>
          <li>
            <strong>UK Parliament Bills API</strong> (bills-api.parliament.uk) — bill title, the House it is currently
            before, its current stage, and whether it has received Royal Assent.
          </li>
        </ul>
      </section>

      <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
        <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">Important Limitations</h4>
        <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
          <li>
            <strong>Select committee evidence:</strong> Oral evidence taken by select committees is published
            separately from Hansard and is not covered. Only Public Bill Committee proceedings are included.
          </li>
          <li>
            <strong>Publication lag:</strong> Hansard for a sitting is published progressively rather than instantly,
            so the most recent proceedings may not yet be retrievable.
          </li>
          <li>
            <strong>Westminster only:</strong> {botName} does not cover the Scottish Parliament, the Senedd, or the
            Northern Ireland Assembly.
          </li>
          <li>
            <strong>Not the statute book:</strong> Hansard records what was <em>said</em> in Parliament, which is not
            the same as what the law <em>is</em>. For the text of an Act or SI, and for its current in-force status,
            consult the legislation assistant.
          </li>
        </ul>
      </section>
    </>
  );
}

export default function DataSourcesModal({
  botName, onClose, isParliament = false, isWestminster = false, scottishJudgments = false,
}) {
  return (
    <Modal onClose={onClose} className="max-w-3xl w-full max-h-[90vh] flex flex-col">
      <div className="flex justify-between items-center p-6 border-b border-ink-200 flex-shrink-0">
        <h2 className="text-xl font-bold text-ink-900">Data Sources</h2>
        <button
          onClick={onClose}
          className="size-[30px] flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          aria-label="Close"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="w-6 h-6"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="overflow-y-auto p-6 space-y-6 text-sm text-ink-700">
        {isWestminster ? (
          <WestminsterSources botName={botName} />
        ) : isParliament ? (
          <HolyroodSources botName={botName} />
        ) : (
          <LegislationSources botName={botName} scottishJudgments={scottishJudgments} />
        )}
      </div>
      <div className="flex justify-end p-4 border-t border-ink-200 flex-shrink-0">
        <button
          onClick={onClose}
          className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
        >
          Close
        </button>
      </div>
    </Modal>
  );
}
