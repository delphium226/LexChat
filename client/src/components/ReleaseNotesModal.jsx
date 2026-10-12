import Modal from './ui/Modal';

// "Release notes" (Settings menu): what has changed for users since the pre-pilot,
// in plain language, and the exact version and build this server runs (moved here
// from the About box, 2026-10-12, so a problem report can name the build).
//
// UPDATE THIS ON EVERY RELEASE: add a row to RELEASES (newest first) and, where the
// release changes what users see, a line in the sections below. The same text is
// published as the "AILA: what's new since the pre-pilot" doc. The detailed sections
// describe the legislation assistant; the parliamentary assistants show the table.

const RELEASES = [
  [
    '2026.10.3',
    '12 October 2026',
    'A Data Sources screen that says what is actually searched, and these release notes in the Settings menu',
  ],
  ['2026.10.2', '12 October 2026', 'Scottish judgments switched on; no other change to answers'],
  [
    '2026.10.1',
    '10 October 2026',
    'The made-under record and revocations, commencement dates, schedules, case law most relevant first, Scotland as the default jurisdiction, a truer sources list',
  ],
  [
    '2026.09.3',
    '29 September 2026',
    'A direct check of whether an instrument is held, lost research steps reported as lost, interpretation given as a reading, summaries kept to their source',
  ],
  ['2026.09.2', '23 September 2026', 'Replies keep the subsections the research found'],
  [
    '2026.09.1',
    '22 September 2026',
    'A working jurisdiction filter, "not found" explained, no unsupported in-force claims, subsection citations and links',
  ],
];

function Item({ title, children }) {
  return (
    <li>
      <strong className="text-ink-900">{title}</strong> {children}
    </li>
  );
}

function Section({ title, lead, children }) {
  return (
    <section>
      <h3 className="text-base font-bold text-ink-900 mb-1">{title}</h3>
      {lead && <p className="mb-2">{lead}</p>}
      <ul className="list-disc list-outside pl-5 space-y-1.5">{children}</ul>
    </section>
  );
}

function LegislationNotes({ botName, scottishJudgments }) {
  return (
    <>
      <p>
        Since the pre-pilot ended in August, {botName} has been improved in six releases, from 22 September to 12
        October 2026. Its answers are now more precise, more complete and plainer about what they could and could not
        check.
      </p>

      <section>
        <h3 className="text-base font-bold text-ink-900 mb-1">In short</h3>
        <ol className="list-decimal list-outside pl-5 space-y-1.5">
          <Item title="When it cannot find something, it says what it searched.">
            A gap in its database is no longer presented as proof that the law does not exist.
          </Item>
          <Item title="It no longer says legislation is in force unless a record supports it.">
            Where legislation.gov.uk records a commencement date, {botName} now gives it.
          </Item>
          <Item title="Citations are more precise.">
            Answers cite the subsection or schedule paragraph, and the link goes to that provision.
          </Item>
          <Item title="You can ask what was made under a section of an Act.">
            {botName} gives the full list of instruments, and says which have been revoked.
          </Item>
          <Item title="Scotland is the default.">
            A question that names no jurisdiction is answered for Scotland, and the answer says so.
          </Item>
        </ol>
      </section>

      <Section
        title="Clearer about what was and was not found"
        lead={`${botName} is now open about the limits of every search, so you can tell a real absence from a gap in what it can see.`}
      >
        <Item title="A line under each answer says what was searched.">
          It names the searches run and their limits, including that the legislation database is incomplete.
        </Item>
        <Item title="An instrument it does not hold is no longer treated as a wrong citation.">
          If you cite an instrument by number and {botName} does not hold it, it says so, and that this does not show
          whether your citation is right. Where it can, it reads the instrument from legislation.gov.uk instead, and
          tells you.
        </Item>
        <Item title="A research step that stopped early, or whose reply was lost, is reported as such.">
          It is no longer reported as having found nothing.
        </Item>
        <Item title="Case law it did not search is not reported as absent.">
          If case law was not searched, the answer says so. If it was, the answer says a search can miss a judgment.
        </Item>
        <Item title="Summaries keep to their source.">
          When {botName} condenses a long document, it no longer adds conclusions, legislation or case citations the
          document does not contain.
        </Item>
        <Item title="A point of interpretation is given as a reading, not as settled law.">
          {botName} does not say a general rule applies, such as an interpretation Act or a doctrine, unless it found
          the provision that applies it.
        </Item>
        <Item title={'No more "You are absolutely right" before anything is checked.'} />
      </Section>

      <Section
        title="Legislation: more precise and more complete answers"
        lead="Answers about legislation now go deeper into the text and say more about how it has changed."
      >
        <Item title="Citations at the right level.">
          {botName} cites the subsection or paragraph it relies on, and the link opens that provision. Related
          subsections the research found are no longer dropped from the reply.
        </Item>
        <Item title="Schedules and annexes are included.">
          When {botName} reads an instrument in full, its schedules and annexes now come with it; before, they were
          always left out. A schedule paragraph asked for by number is fetched directly. Long schedules are still being
          improved.
        </Item>
        <Item title="The record of changes.">
          {botName} can tell you which later legislation amended, brought into force, repealed or revoked a provision.
          Each change stays with the provision that made it.
        </Item>
        <Item title="Commencement dates.">
          Where legislation.gov.uk records the date a provision was brought into force, {botName} gives it, with any
          qualification such as "for specified purposes". A commencement date is never presented as proof that a
          provision is in force today.
        </Item>
        <Item title="In-force status is stated only from the record.">
          {botName} no longer reads in-force status from the version of the text it holds. It says a provision is "not
          recorded as commenced" only where the record is complete.
        </Item>
        <Item title="Removals are read by kind.">
          A provision repealed is told apart from words removed from a provision that stays, and from a repeal that is
          prospective, temporary or partial.
        </Item>
        <Item title="What an instrument was made under">
          is stated only where {botName} has read the instrument's own words saying so.
        </Item>
        <Item title="The jurisdiction filter now works.">
          It used to drop most search results silently. A question that names no jurisdiction is answered for
          Scotland; a question about the UK is answered for each nation, saying where the law differs.
        </Item>
        <Item title="Search results carry each instrument's own short summary,">
          which often says when it came into force or what it was made under.
        </Item>
      </Section>

      <Section
        title="New: what was made under a section, and what has been revoked"
        lead={`You can now ask "which regulations were made under section N of this Act?" and get the full list. Before, ${botName} could only run a keyword search, which found a handful at best.`}
      >
        <Item title="How it works.">
          {botName} holds a record of what each statutory instrument's own opening words say it was made under. It
          covers Scottish statutory instruments made from 1999 and UK statutory instruments made from 1987, including
          Welsh statutory instruments and Northern Ireland Orders in Council: about 87,000 instruments.
        </Item>
        <Item title="What an answer tells you.">
          The total, each instrument with a link, and what the record covers. If none is found, {botName} says what the
          record covers rather than that nothing was made.
        </Item>
        <Item title="Which have been revoked.">
          Each listed instrument says whether legislation.gov.uk records it as revoked in whole (by which instrument,
          and from when), revoked in part, or not at all, with the date this was checked. A revocation that takes
          effect in future is given with its date.
        </Item>
        <Item title={'"No revocation recorded" is not "in force".'}>
          {botName} never treats the absence of a recorded revocation as confirmation that an instrument still has
          effect.
        </Item>
        <Item title="Long lists.">
          Where more than 40 instruments are found, the list shown leads with those not revoked in whole.
        </Item>
        <Item title="Not covered:">instruments made before 1987, which are mostly published only as scanned images.</Item>
      </Section>

      <Section
        title={scottishJudgments ? 'Case law: better searches, and Scottish judgments added' : 'Case law: better searches'}
        lead={
          scottishJudgments
            ? 'Case-law searches now find the most relevant judgments, and Scottish court decisions are now included.'
            : 'Case-law searches now find the most relevant judgments.'
        }
      >
        <Item title="Most relevant first.">
          Search results used to come back newest first, so older leading cases could be missed. They now come back
          most relevant first.
        </Item>
        <Item title="Date ranges work.">A date range on a case-law search was previously ignored. It now applies.</Item>
        <Item title="The true number of matches.">
          {botName} now knows how many judgments matched, not only how many it was shown, and says what its search
          covered.
        </Item>
        <Item title="A named case that was not found.">
          If you name a case and the search does not return it, {botName}'s research is now told it was not found, so
          that it does not describe what the case decided as though it had read the judgment.
        </Item>
        {scottishJudgments ? (
          <Item title="Scottish judgments.">
            {botName} now also searches the judgments published by the Scottish Courts and Tribunals Service, so a
            question of Scots law can be answered from Scottish decisions: the Court of Session, High Court of
            Justiciary, Sheriff Appeal Court, published sheriff court decisions and Scottish tribunals, from 1998.
            Appeals from Scotland to the UK Supreme Court remain covered as before.
          </Item>
        ) : (
          <Item title="Scottish judgments are coming.">
            {botName} can search the judgments published by the Scottish Courts and Tribunals Service once it is
            switched on for your organisation. Until then, answers say which Scottish courts are not covered; UK
            Supreme Court appeals from Scotland already are.
          </Item>
        )}
      </Section>

      <Section
        title={`Using ${botName}: settings, sources and reliability`}
        lead={`${botName} is easier to steer, and its answers show their sources more faithfully.`}
      >
        <Item title="Getting case law included.">
          When a question needs case law and it is not switched on, {botName} now names the right control: Filters,
          then Research type, then Legislation &amp; case law. It notices when you change a setting, and its
          suggestion buttons no longer offer to change settings they cannot change.
        </Item>
        <Item title="The sources list matches the answer.">
          It shows the sources the answer relies on, each by its title, rather than every search result. Instruments
          the answer names carry the links the research found.
        </Item>
        <Item title="No blank or lost replies.">
          If the AI service fails part-way, {botName} recovers sooner and tells you what happened, rather than leaving
          an empty answer.
        </Item>
        <Item title="Deep Research steps build on each other.">
          Each step is handed what the earlier steps found, instead of searching for it again.
        </Item>
        <Item title="One search line, not two,">under each answer.</Item>
        <Item title="Know what it searches.">
          Settings, then Data Sources, now describes exactly what {botName} searches and the limits of each source.
          These release notes are under Settings too, with the version and build your server runs.
        </Item>
      </Section>
    </>
  );
}

export default function ReleaseNotesModal({ botInfo, onClose, isParliament = false }) {
  const botName = botInfo.name;
  return (
    <Modal onClose={onClose} className="max-w-3xl w-full max-h-[90vh] flex flex-col">
      <div className="flex justify-between items-center p-6 border-b border-ink-200 flex-shrink-0">
        <h2 className="text-xl font-bold text-ink-900">Release notes</h2>
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
        {isParliament ? (
          <p>
            The releases below mostly improve the legislation assistant. {botName} runs on the same release, so its
            version is listed here too.
          </p>
        ) : (
          <LegislationNotes botName={botName} scottishJudgments={botInfo.scottishJudgments} />
        )}

        <section>
          <h3 className="text-base font-bold text-ink-900 mb-2">Releases</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-ink-200 text-ink-900">
                  <th className="py-2 pr-4 font-semibold whitespace-nowrap">Release</th>
                  <th className="py-2 pr-4 font-semibold whitespace-nowrap">Date</th>
                  <th className="py-2 font-semibold">What it brought</th>
                </tr>
              </thead>
              <tbody>
                {RELEASES.map(([ver, date, what]) => (
                  <tr key={ver} className="border-b border-ink-100 align-top">
                    <td className="py-2 pr-4 font-mono whitespace-nowrap">{ver}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">{date}</td>
                    <td className="py-2">{what}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            A release reaches you once it is installed on your organisation's server. {botName} remains a proof of
            concept: check its answers before relying on them.
          </p>
        </section>
      </div>
      <div className="flex justify-between items-center gap-4 p-4 border-t border-ink-200 flex-shrink-0">
        {/* The release this server runs, and its exact build (git describe: the
            release tag itself, or the tag plus the commits past it), so a problem
            report can name both. */}
        <span className="font-ui text-xs text-ink-600">
          {botInfo.version && <>Version {botInfo.version}</>}
          {botInfo.build && <> · Build {botInfo.build}</>}
        </span>
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
