import React, { useState } from 'react';
import { getSessionFeedback, getSessionDurations, getSessionTranscripts } from '../../services/api';
import { Card, SectionHeader } from '../../components/ui/Card';
import { toCsv, downloadCsv, csvDateStamp } from '../../utils/csv';
import {
  SESSION_EXPORT_COLUMNS,
  TRANSCRIPT_COLUMNS,
  TIMEFRAME_OPTIONS,
  buildTranscriptRows,
  timeframeSlug,
} from './sessionFeedbackExport';

/**
 * The session-feedback export with the full thread attached (Developer tab).
 *
 * The Session Feedback tab exports what the lawyer SAID about a session; this
 * exports that alongside what actually happened in it, so an answer to "the
 * assistant referred to the wrong Act" can be read against the answer that
 * prompted it. Same columns, same population, same timeframes — the transcript
 * columns are appended, making this file a strict superset of that one.
 *
 * ONE ROW PER MESSAGE, not one row per session with the thread in a single
 * cell. Excel truncates a cell past 32,767 characters silently, which a single
 * Deep Research report can exceed on its own — the shape that reads most
 * naturally is the one that would quietly lose evidence. Long format also lets
 * a reader filter to `Message role = user` to see just the queries.
 *
 * Lives on the Developer tab rather than beside the export it extends because
 * it pulls every message of every reported thread: an admin-only bulk read of
 * user content, deliberately kept behind a deliberate press rather than
 * offered next to the ordinary one.
 *
 * Fetches its own data on click. The Developer tab holds no feedback state, and
 * loading transcripts with the tab would mean every visit pulls the corpus for
 * an export nobody may take.
 */
export const TranscriptExport = () => {
  const [timeframe, setTimeframe] = useState('30');
  const [isExporting, setIsExporting] = useState(false);
  const [message, setMessage] = useState(null);

  const handleExport = async () => {
    setIsExporting(true);
    setMessage(null);
    try {
      // The three reads the file joins. All are filtered on when the form
      // arrived, so one timeframe describes the same sessions in each.
      const [rows, durations, transcripts] = await Promise.all([
        getSessionFeedback(timeframe),
        getSessionDurations(timeframe),
        getSessionTranscripts(timeframe),
      ]);
      if (!rows.length) {
        setMessage({ tone: 'warn', text: 'No session feedback in this period — nothing to export.' });
        return;
      }
      const exportRows = buildTranscriptRows(rows, durations?.sessions, transcripts);
      downloadCsv(
        `session-transcripts-${timeframeSlug(timeframe)}-${csvDateStamp()}.csv`,
        toCsv(exportRows, [...SESSION_EXPORT_COLUMNS, ...TRANSCRIPT_COLUMNS])
      );
      const withText = exportRows.filter(r => r._msg).length;
      setMessage({
        tone: 'success',
        text: `Exported ${rows.length} ${rows.length === 1 ? 'response' : 'responses'} as ${exportRows.length} ${
          exportRows.length === 1 ? 'row' : 'rows'
        } (${withText} ${withText === 1 ? 'message' : 'messages'}).`,
      });
    } catch (error) {
      setMessage({
        tone: 'danger',
        text: error?.response?.data?.detail || 'Export failed. The transcripts could not be fetched.',
      });
    } finally {
      setIsExporting(false);
    }
  };

  const toneClass = {
    success: 'text-success',
    warn: 'text-warn',
    danger: 'text-danger',
  };

  return (
    <Card>
      <SectionHeader
        title="Session Feedback + Transcripts Export"
        description={
          <>
            The Session Feedback tab&rsquo;s export with the whole thread attached — every query and
            every answer of each reported session, one row per message, with that session&rsquo;s
            feedback answers repeated across its rows. Join it to the plain export on{' '}
            <span className="font-ui text-xs">Session ID</span>. Contains the full text of
            users&rsquo; queries and the assistant&rsquo;s answers, so treat the file as you would
            the chat history itself.
          </>
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-ink-500 mb-1">Timeframe</label>
          <select
            value={timeframe}
            onChange={e => setTimeframe(e.target.value)}
            disabled={isExporting}
            className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-accent disabled:opacity-50"
          >
            {TIMEFRAME_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isExporting ? 'Preparing…' : 'Export CSV'}
        </button>
        {message && <p className={`text-sm ${toneClass[message.tone]}`}>{message.text}</p>}
      </div>

      <p className="text-xs text-ink-400 mt-4">
        A wide timeframe pulls every message of every reported thread and can take a few seconds. Sessions whose
        messages have since been cleared still appear, as a single row with the message columns blank — a response is
        never dropped for want of a transcript.
      </p>
    </Card>
  );
};

export default TranscriptExport;
