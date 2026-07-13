import Modal from './ui/Modal';

// Static reference modal describing the legislation & case law data sources.
// Content is entirely static apart from the bot name.
export default function DataSourcesModal({ botName, onClose }) {
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
