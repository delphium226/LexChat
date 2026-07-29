import Modal from './ui/Modal';

// Reference modal describing the data sources the bot actually queries. The
// same client serves three bots with entirely disjoint sources, so the body is
// selected per-bot rather than shared — only the bot name is interpolated.

// --- Legislation bot: LEX / legislation.gov.uk + TNA Find Case Law ----------
function LegislationSources({ botName }) {
  return (
    <>
      {/* Legislation API */}
      <section>
        <h3 className="text-base font-bold text-ink-900 mb-2">
          Source Overview: The National Archives "Legislation" API
        </h3>
        <p>
          {botName} connects to the official API for legislation.gov.uk, operated by The National Archives. This
          database serves as the official, government-maintained statute book for the United Kingdom. Through this
          integration, {botName} can retrieve and analyze the text of laws, regulations, and statutory rules.
        </p>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Jurisdictions and Parliaments Covered</h4>
        <p className="mb-2">
          Unlike the Case Law database, the Legislation API provides comprehensive coverage across all four nations of
          the UK. {botName} can retrieve legislation from:
        </p>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>The UK Parliament (Westminster)</li>
          <li>The Scottish Parliament (Holyrood)</li>
          <li>The Welsh Parliament / Senedd Cymru</li>
          <li>The Northern Ireland Assembly</li>
        </ul>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Types of Legislation Included</h4>
        <p className="mb-2">
          {botName} has access to both primary laws (the main Acts) and secondary legislation (the detailed rules and
          regulations):
        </p>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>Primary Legislation:</strong> Public General Acts of the UK Parliament, Acts of the Scottish
            Parliament (ASPs), Acts/Measures of the Senedd Cymru, and Acts of the Northern Ireland Assembly.
          </li>
          <li>
            <strong>Secondary Legislation:</strong> Statutory Instruments (SIs), Scottish Statutory Instruments
            (SSIs), and Welsh Statutory Instruments.
          </li>
          <li>
            <strong>Historical EU Law:</strong> "Retained EU legislation" that was incorporated into UK domestic law
            following Brexit.
          </li>
        </ul>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Versioning: "As Enacted" vs. "Revised"</h4>
        <p className="mb-2">
          One of the most powerful features of this database is how it handles the timeline of the law. {botName} can
          distinguish between:
        </p>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>As Enacted:</strong> The original text of the law exactly as it was originally passed by
            Parliament.
          </li>
          <li>
            <strong>Latest Available (Revised):</strong> The current, up-to-date version of the law, reflecting any
            amendments, insertions, or repeals made by subsequent legislation.
          </li>
        </ul>
      </section>

      <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
        <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">
          Important Limitations (The "Revision Gap")
        </h4>
        <p className="mb-2 text-amber-900 dark:text-amber-200">
          To ensure users interpret the law correctly, it is important to understand a key limitation of the official
          UK statute book:
        </p>
        <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
          <li>
            <strong>Delayed Revisions:</strong> While the National Archives team works constantly to update the
            database, there is often a "revision gap." When a new law amends an old law, it can take time (sometimes
            months or, for obscure legislation, years) for those changes to be officially applied to the "Revised"
            text on the database.
          </li>
          <li>
            <strong>Repealed Text:</strong> {botName} may retrieve legislation that has been entirely repealed or is
            no longer in force if you specifically ask for historical context, so always verify the current legal
            status of older statutes.
          </li>
        </ul>
      </section>

      <div className="border-t border-ink-200 pt-6">
        <h3 className="text-base font-bold text-ink-900 mb-2">
          Source Overview: The National Archives "Find Case Law" API
        </h3>
        <p>
          Alongside legislation, {botName} integrates with The National Archives (TNA) "Find Case Law" API. This is
          the official, government-backed repository for court judgments and tribunal decisions in the United Kingdom.
          By connecting directly to this source, {botName} ensures that the case law it references is authoritative,
          unmodified, and publicly verifiable.
        </p>
      </div>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Courts and Tribunals Covered</h4>
        <p className="mb-2">
          The API primarily covers the higher courts of England and Wales, alongside the highest appellate courts for
          the entire UK. Through this integration, {botName} can retrieve judgments from:
        </p>
        <div className="space-y-3 pl-2">
          <div>
            <p className="font-medium text-ink-800">UK-Wide Appellate Courts:</p>
            <ul className="list-disc list-inside space-y-1 pl-4">
              <li>The UK Supreme Court (UKSC)</li>
              <li>The Judicial Committee of the Privy Council (JCPC)</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-ink-800">England &amp; Wales Higher Courts:</p>
            <ul className="list-disc list-inside space-y-1 pl-4">
              <li>Court of Appeal (Civil and Criminal Divisions)</li>
              <li>High Court of Justice (King's Bench, Chancery, and Family Divisions)</li>
              <li>Courts Martial Appeal Court</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-ink-800">UK Tribunals:</p>
            <ul className="list-disc list-inside space-y-1 pl-4">
              <li>
                Upper Tribunal (Administrative Appeals, Immigration and Asylum, Lands, and Tax and Chancery Chambers)
              </li>
              <li>Employment Appeal Tribunal (EAT)</li>
            </ul>
          </div>
        </div>
      </section>

      <section>
        <h4 className="font-semibold text-ink-900 mb-2">Temporal Coverage (Dates)</h4>
        <ul className="list-disc list-inside space-y-1 pl-2">
          <li>
            <strong>Modern Judgments:</strong> The database is highly comprehensive for cases handed down from 2003
            onwards.
          </li>
          <li>
            <strong>Recent Cases:</strong> Newly published judgments are added to the database shortly after being
            handed down by the courts.
          </li>
          <li>
            <strong>Historical Cases:</strong> While not a complete historical archive, the database is continually
            expanding to include significant landmark judgments from before 2003.
          </li>
        </ul>
      </section>

      <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
        <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">
          Important Limitations (What is NOT Covered)
        </h4>
        <p className="mb-2 text-amber-900 dark:text-amber-200">
          To ensure you get the most out of {botName}, it is important to know which jurisdictions and courts are not
          currently available through this official API:
        </p>
        <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
          <li>
            <strong>Scotland and Northern Ireland:</strong> The API does not host judgments from the domestic courts
            of Scotland (e.g., Court of Session, High Court of Justiciary) or Northern Ireland, except when those
            cases are appealed to the UK Supreme Court.
          </li>
          <li>
            <strong>Lower Courts:</strong> Judgments from the Crown Court, County Courts, Magistrates' Courts, and
            Family Court are generally not published or available through this API.
          </li>
          <li>
            <strong>First-Tier Tribunals:</strong> Decisions from lower-level tribunals (like the Employment Tribunal
            or First-tier Immigration Tribunals) are currently excluded.
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

export default function DataSourcesModal({ botName, onClose, isParliament = false, isWestminster = false }) {
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
          <LegislationSources botName={botName} />
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
