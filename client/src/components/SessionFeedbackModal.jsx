import React, { useEffect, useRef, useState } from 'react';
import Modal from './ui/Modal';
import { submitSessionFeedback } from '../services/api';

// End-of-session feedback form for the pre-pilot. Opened from the "Finished
// session" button in the chat top bar (gated by the session_feedback_enabled
// feature flag). Question numbering follows the agreed pre-pilot document.
//
// Every field is optional — the form is long and a lawyer may only want to
// answer part of it — so Submit is blocked only when nothing at all has been
// filled in, which stops an accidental click writing a blank row.

const LABEL = 'block font-ui text-xs font-semibold uppercase tracking-wide text-ink-600 mb-1.5';
const INPUT =
  'w-full border border-ink-200 rounded-sm px-3 py-2 font-ui text-sm bg-paper text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent disabled:opacity-60';
const SECTION = 'font-ui text-sm font-semibold text-ink-900 border-b border-ink-200 pb-1.5 mb-3';

function Field({ label, children }) {
  return (
    <div className="mb-3">
      <label className={LABEL}>{label}</label>
      {children}
    </div>
  );
}

function HoursInput({ value, onChange, placeholder, disabled }) {
  return (
    <input
      type="number"
      min="0"
      step="0.1"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className={INPUT}
    />
  );
}

function TextArea({ value, onChange, placeholder, disabled, rows = 2 }) {
  return (
    <textarea
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      disabled={disabled}
      className={`${INPUT} resize-y`}
    />
  );
}

// Horizontal button group for the closed questions. Clicking the selected
// option clears it, matching the scale behaviour in the weekly survey.
function OptionRow({ options, value, onChange, disabled }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(opt => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(active ? null : opt.value)}
            className={`font-ui text-sm rounded-md px-3 py-1.5 border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60 ${
              active
                ? 'bg-accent border-accent text-white'
                : 'bg-paper border-ink-200 text-ink-700 hover:bg-ink-50'
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// Numbered 1..max scale with anchor labels. Both Q8 and Q9a are 1-5.
//
// The caption line below the buttons shows the selected anchor once there is
// one and the two endpoints before that — in a narrow column there is no room
// for an inline label, and without the endpoints the user cannot tell which
// end is which until they click.
function ScaleRow({ max, anchors, value, onChange, disabled }) {
  const numbers = Array.from({ length: max }, (_, i) => i + 1);
  return (
    <div style={{ maxWidth: max * 38 }}>
      <div className="flex items-center gap-1.5">
        {numbers.map(n => {
          const active = value !== null && value >= n;
          return (
            <button
              key={n}
              type="button"
              disabled={disabled}
              title={anchors[n - 1]}
              onClick={() => onChange(value === n ? null : n)}
              className={`size-8 rounded-md border font-ui text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60 ${
                active ? 'bg-accent border-accent text-white' : 'bg-paper border-ink-300 text-ink-500 hover:bg-ink-50'
              }`}
            >
              {n}
            </button>
          );
        })}
      </div>
      {value !== null ? (
        <p className="font-ui text-xs text-ink-600 mt-1">{anchors[value - 1]}</p>
      ) : (
        <div className="flex justify-between font-ui text-xs text-ink-400 mt-1">
          <span>{anchors[0]}</span>
          <span>{anchors[max - 1]}</span>
        </div>
      )}
    </div>
  );
}

// Each Accuracy question carries a free-text box, shown whatever the answer —
// the reasoning behind a "yes" is as useful to the pre-pilot as a complaint.
const OBSERVATIONS = n => `${n}. Observations in support of your answer`;

const YES_PARTIALLY_NO = [
  { value: 'yes', label: 'Yes' },
  { value: 'partially', label: 'Partially' },
  { value: 'no', label: 'No' },
];

const CONFIDENCE_ANCHORS = [
  'Not at all confident',
  'Slightly confident',
  'Somewhat confident',
  'Fairly confident',
  'Very confident',
];
const EASE_ANCHORS = ['Very difficult', 'Somewhat difficult', 'Neither easy nor difficult', 'Somewhat easy', 'Very easy'];

const SessionFeedbackModal = ({ chatId, messageCount, botName = 'AILA', onClose, onSubmitted }) => {
  const [manualTime, setManualTime] = useState('');
  const [timeSaved, setTimeSaved] = useState('');
  const [continuity, setContinuity] = useState(null);
  const [verification, setVerification] = useState('');
  const [foundLaw, setFoundLaw] = useState(null);
  const [foundLawNotes, setFoundLawNotes] = useState('');
  const [refsAccurate, setRefsAccurate] = useState(null);
  const [refsNotes, setRefsNotes] = useState('');
  const [statedLaw, setStatedLaw] = useState(null);
  const [statedLawNotes, setStatedLawNotes] = useState('');
  const [confidence, setConfidence] = useState(null);
  const [ease, setEase] = useState(null);
  const [easeReason, setEaseReason] = useState('');
  const [comments, setComments] = useState('');
  const [status, setStatus] = useState('idle');

  // The modal only mounts when "Finished session" is pressed, so mount time is
  // the press. Sent as an elapsed delta rather than a timestamp so a skewed
  // client clock can't land a wrong session end in the DB — only the short
  // local interval has to be right, and it excludes the form-filling time.
  // Stamped in an effect rather than in useRef's initialiser: Date.now() is
  // impure and must not be called during render.
  const openedAtRef = useRef(null);
  useEffect(() => {
    openedAtRef.current = Date.now();
  }, []);

  const busy = status === 'submitting';
  const num = v => (v !== '' ? parseFloat(v) : null);
  const txt = v => v.trim() || null;

  const isEmpty =
    [manualTime, timeSaved, verification, foundLawNotes, refsNotes, statedLawNotes, easeReason, comments].every(
      v => v.trim() === ''
    ) && [continuity, foundLaw, refsAccurate, statedLaw, confidence, ease].every(v => v === null);

  const handleSubmit = async () => {
    setStatus('submitting');
    try {
      await submitSessionFeedback({
        chat_id: chatId ?? null,
        message_count: messageCount ?? null,
        manual_time_hours: num(manualTime),
        time_saved_hours: num(timeSaved),
        verification_hours: num(verification),
        session_continuity: continuity,
        found_right_law: foundLaw,
        found_right_law_notes: txt(foundLawNotes),
        references_accurate: refsAccurate,
        references_notes: txt(refsNotes),
        stated_law_correctly: statedLaw,
        stated_law_notes: txt(statedLawNotes),
        confidence,
        ease_of_use: ease,
        ease_of_use_reason: txt(easeReason),
        other_comments: txt(comments),
        finished_seconds_ago: openedAtRef.current
          ? Math.max(0, Math.round((Date.now() - openedAtRef.current) / 1000))
          : 0,
      });
      if (onSubmitted) onSubmitted();
      setStatus('success');
      setTimeout(onClose, 1800);
    } catch {
      setStatus('error');
    }
  };

  return (
    <Modal
      onClose={busy ? undefined : onClose}
      dismissable={!busy}
      className="max-w-5xl w-full max-h-[90vh] overflow-y-auto p-6"
    >
      <div className="flex justify-between items-start gap-4 mb-1">
        <h3 className="font-ui text-xl font-semibold text-ink-900">How did this session go?</h3>
        <button
          onClick={onClose}
          disabled={busy}
          aria-label="Close"
          className="size-[30px] flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
        >
          <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {status === 'success' ? (
        <p className="font-ui text-sm text-ink-600 py-8 text-center">Thank you — your feedback has been recorded.</p>
      ) : (
        <>
          <p className="font-ui text-sm text-ink-500 mb-2">
            Your answers help us to improve {botName} to make it more accurate and useful
          </p>

          {/* Landscape: the three sections sit side by side so the whole form
              fits one screen without scrolling. Falls back to one column on a
              narrow window; the modal keeps overflow-y-auto as a safety net. */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8">
            <div>
              <h4 className={SECTION}>Time</h4>

              <Field label="1. How much time would it have taken you to complete this same task manually? (hours)">
                <HoursInput value={manualTime} onChange={setManualTime} placeholder="e.g. 4.0" disabled={busy} />
              </Field>

              <Field label={`2. By using ${botName}, how much time do you estimate you saved? (hours)`}>
                <HoursInput value={timeSaved} onChange={setTimeSaved} placeholder="e.g. 1.5" disabled={busy} />
              </Field>

              <Field label="3. Did you do this session in one go, or did you do other work or take a break in between queries?">
                <OptionRow
                  options={[
                    { value: 'one_go', label: 'In one go' },
                    { value: 'not_one_go', label: 'Not in one go' },
                  ]}
                  value={continuity}
                  onChange={setContinuity}
                  disabled={busy}
                />
              </Field>

              <Field label={`4. How much time did you spend checking ${botName}'s outputs? (hours)`}>
                <HoursInput value={verification} onChange={setVerification} placeholder="e.g. 0.5" disabled={busy} />
              </Field>
            </div>

            <div className="md:border-l md:border-ink-100 md:pl-8">
              <h4 className={SECTION}>Accuracy</h4>

              <Field label={`5a. Did ${botName} find the right legislation?`}>
                <OptionRow options={YES_PARTIALLY_NO} value={foundLaw} onChange={setFoundLaw} disabled={busy} />
              </Field>

              <Field label={OBSERVATIONS('5b')}>
                <TextArea
                  value={foundLawNotes}
                  onChange={setFoundLawNotes}
                  placeholder="Which legislation was found or missed, and what went wrong…"
                  disabled={busy}
                />
              </Field>

              <Field label={`6a. Did ${botName} provide real and accurate references?`}>
                <OptionRow
                  options={[
                    { value: 'yes', label: 'Yes' },
                    { value: 'no', label: 'No' },
                    { value: 'unsure', label: 'Unsure' },
                  ]}
                  value={refsAccurate}
                  onChange={setRefsAccurate}
                  disabled={busy}
                />
              </Field>

              <Field label={OBSERVATIONS('6b')}>
                <TextArea
                  value={refsNotes}
                  onChange={setRefsNotes}
                  placeholder="Note any citation that was wrong, invented or out of date…"
                  disabled={busy}
                />
              </Field>

              <Field
                label={`7a. Did ${botName} state the legislation correctly without including unsupported information?`}
              >
                <OptionRow options={YES_PARTIALLY_NO} value={statedLaw} onChange={setStatedLaw} disabled={busy} />
              </Field>

              <Field label={OBSERVATIONS('7b')}>
                <TextArea
                  value={statedLawNotes}
                  onChange={setStatedLawNotes}
                  placeholder="What was overstated, unsupported, or well evidenced…"
                  disabled={busy}
                />
              </Field>
            </div>

            <div className="lg:border-l lg:border-ink-100 lg:pl-8">
              <h4 className={SECTION}>Experience</h4>

              <Field label={`8. Rate your overall confidence in ${botName}'s answer`}>
                <ScaleRow
                  max={5}
                  anchors={CONFIDENCE_ANCHORS}
                  value={confidence}
                  onChange={setConfidence}
                  disabled={busy}
                />
              </Field>

              <Field label={`9a. Rate how easy or difficult you found it to use ${botName}`}>
                <ScaleRow max={5} anchors={EASE_ANCHORS} value={ease} onChange={setEase} disabled={busy} />
              </Field>

              <Field label="9b. Please explain the reason for your rating">
                <TextArea
                  value={easeReason}
                  onChange={setEaseReason}
                  placeholder="What made it easy or difficult…"
                  disabled={busy}
                />
              </Field>

              <Field label={`10. Any other comments? What would make ${botName} better?`}>
                <TextArea
                  value={comments}
                  onChange={setComments}
                  placeholder="Anything else you'd like us to know…"
                  rows={3}
                  disabled={busy}
                />
              </Field>
            </div>
          </div>

          {status === 'error' && (
            <p className="font-ui text-xs text-danger mb-3">Something went wrong — please try again.</p>
          )}

          <div className="flex justify-end gap-2 pt-3 mt-2 border-t border-ink-100">
            <button
              onClick={onClose}
              disabled={busy}
              className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={busy || isEmpty}
              title={isEmpty ? 'Answer at least one question before submitting' : undefined}
              className="bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy ? 'Submitting…' : 'Submit feedback'}
            </button>
          </div>
        </>
      )}
    </Modal>
  );
};

export default SessionFeedbackModal;
