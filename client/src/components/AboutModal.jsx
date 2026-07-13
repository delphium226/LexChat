import Modal from './ui/Modal';
import { LexMark } from './LexMark';

// Static "About" modal — bot branding + a short description of the architecture.
export default function AboutModal({ botInfo, onClose }) {
  return (
    <Modal onClose={onClose} className="p-6 max-w-2xl w-full">
      <div className="flex items-center justify-center gap-2 mb-4">
        {botInfo.logoEmoji ? (
          <span style={{ fontSize: 32, lineHeight: 1, userSelect: 'none' }} aria-hidden="true">
            {botInfo.logoEmoji}
          </span>
        ) : (
          <LexMark size={32} color={botInfo.brandColor || 'var(--accent)'} />
        )}
        <h1 className="text-3xl font-bold" style={{ color: botInfo.brandColor || 'var(--accent)' }}>
          {botInfo.name}
        </h1>
      </div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-ink-900">About {botInfo.name}</h2>
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
      <div className="space-y-4 text-ink-700 text-sm">
        <p>
          <strong>{botInfo.name}</strong> is an intelligent legal research assistant for UK legislation and case law.
        </p>
        <div>
          <h3 className="font-semibold text-ink-900 mb-1">Data Sources</h3>
          <ul className="list-disc list-inside">
            <li>
              <strong>The National Archives</strong> (legislation.gov.uk)
            </li>
          </ul>
        </div>
        <div>
          <h3 className="font-semibold text-ink-900 mb-1">AI Approach</h3>
          <p>
            Agentic RAG architecture — the system queries the LEX API and uses an LLM to provide accurate,
            context-aware answers.
          </p>
        </div>
      </div>
      <div className="mt-6 flex justify-end">
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
