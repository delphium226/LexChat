import React from 'react';
import { LexWordmark } from './LexMark';

const ShieldIcon = () => (
  <svg
    width={22}
    height={22}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.5}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="M12 8v4M12 16h.01" />
  </svg>
);

export default function DataSensitivityNotice({ onAcknowledge, botName = 'AILA', botLogoEmoji = null }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-paper rounded-xl shadow-md border border-ink-200 w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-8 pt-7 pb-5 border-b border-ink-200 flex-shrink-0">
          <LexWordmark size={14} name={botName} logoEmoji={botLogoEmoji || undefined} />
          <span className="font-ui text-xs text-ink-400 uppercase tracking-wide">Pre-use notice</span>
        </div>

        {/* Scrollable body — entirely inside the blue POC container */}
        <div className="overflow-y-auto px-6 py-5 flex-1 lex-scroll">
          <div className="rounded-lg bg-accent-soft border border-accent/30 px-6 py-5 space-y-5">
            {/* POC heading */}
            <div className="text-center pb-1 border-b border-accent/20">
              <p className="font-ui text-sm font-semibold text-accent-ink uppercase tracking-widest mb-1">
                Proof of Concept
              </p>
              <p className="font-ui text-sm text-ink-700 leading-relaxed">
                {botName} is a proof-of-concept system under active development. It is not yet approved for production
                use. Outputs should be treated as indicative only and verified before being relied upon.
              </p>
            </div>

            {/* External processing warning */}
            <div className="flex items-start gap-3">
              <span className="text-accent-ink flex-shrink-0 mt-0.5 opacity-70">
                <ShieldIcon />
              </span>
              <div>
                <p className="font-ui text-sm font-semibold text-ink-900 mb-1">
                  Processing Outside the Organisation's Secure Network
                </p>
                <p className="font-ui text-sm text-ink-700 leading-relaxed">
                  {botName} currently routes queries through large language model (LLM) services hosted by third-party
                  providers outside this organisation's secure network. Text entered into this tool may be transmitted
                  to and processed by those external services.
                </p>
              </div>
            </div>

            {/* Prohibited content */}
            <div>
              <h2 className="font-ui text-sm font-semibold text-ink-900 mb-2">Information You Must Not Enter</h2>
              <p className="font-ui text-sm text-ink-700 leading-relaxed mb-3">
                In accordance with your data-handling obligations and organisational security policy, you must not enter
                any of the following into this tool:
              </p>
              <ul className="space-y-2">
                {[
                  'Information classified above OFFICIAL',
                  'Personal data within the meaning of the UK GDPR — including names, contact details, National Insurance numbers, or any information capable of identifying a living individual, whether directly or in combination with other data',
                  'Details of ongoing legal proceedings, investigations, or enforcement action that are not already in the public domain',
                  'Information subject to legal professional privilege',
                  'Information obtained under a duty of confidence, including that provided by another government department or public body',
                  'Commercially sensitive information, including unpublished contractual terms, tendering details, or negotiating positions',
                  'Any information bearing a protective marking caveat (e.g. SENSITIVE, LEGAL, POLICY)',
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="mt-1.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-accent opacity-60" />
                    <span className="font-ui text-sm text-ink-800 leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Permitted use */}
            <div>
              <h2 className="font-ui text-sm font-semibold text-ink-900 mb-2">Permitted Use</h2>
              <p className="font-ui text-sm text-ink-700 leading-relaxed">
                {botName} is suitable for general legal research using publicly available UK legislation and case law.
                Queries should be framed in general, hypothetical, or anonymised terms. It must not be used as a
                substitute for independent legal advice or judgment on a specific matter.
              </p>
            </div>

            {/* Audit logging */}
            <div>
              <h2 className="font-ui text-sm font-semibold text-ink-900 mb-2">Audit Logging</h2>
              <p className="font-ui text-sm text-ink-700 leading-relaxed">
                All queries and responses are logged and may be reviewed for security, compliance, and quality-assurance
                purposes. Do not assume that any query is private.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-4 px-8 py-5 border-t border-ink-200 bg-ink-25 rounded-b-xl flex-shrink-0">
          <p className="font-ui text-xs text-ink-500 leading-relaxed max-w-sm">
            By proceeding, you confirm that you have read this notice and that your queries will not contain information
            of the types described above.
          </p>
          <button
            onClick={onAcknowledge}
            className="flex-shrink-0 bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-5 py-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
          >
            I understand — proceed to {botName}
          </button>
        </div>
      </div>
    </div>
  );
}
