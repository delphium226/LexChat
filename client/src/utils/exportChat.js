// Whole-conversation clipboard export.
//
// Produces a rich-text (text/html) flavour alongside a plain-text fallback so a
// lawyer can paste a full thread — questions, answers and source citations —
// straight into Word or Outlook with the formatting intact.
//
// Word/Outlook only reliably honour *inline* styles on each element (they drop
// most of a <style> block and ignore flexbox/grid entirely), and they measure in
// points, so everything below is inlined and sized in pt.

import { marked } from 'marked';
import DOMPurify from 'dompurify';

// ── Shared styling ────────────────────────────────────────────────
// Deliberately concrete values, not design tokens: the clipboard target is a
// Word/Outlook document that has no access to our CSS variables.

// Single quotes inside the font stacks are deliberate: these strings are
// interpolated into double-quoted style="…" attributes that we build by hand, so
// an embedded double quote would terminate the attribute and corrupt the markup.
const BODY_FONT = "Georgia, 'Times New Roman', serif";
const UI_FONT = 'Calibri, Arial, sans-serif';
const MONO_FONT = "Consolas, 'Courier New', monospace";
const INK = '#1f2328';
const MUTED = '#5c6570';
const RULE = '#d0d7de';
const LINK = '#0b5cad';

const LABEL_STYLE = `margin:0 0 4pt;font-family:${UI_FONT};font-size:8.5pt;font-weight:bold;letter-spacing:0.06em;text-transform:uppercase;color:${MUTED};`;
const QUESTION_STYLE = `margin:0 0 6pt;font-family:${UI_FONT};font-size:11pt;font-weight:bold;line-height:1.45;color:${INK};`;
const META_STYLE = `margin:0 0 10pt;font-family:${UI_FONT};font-size:9pt;color:${MUTED};`;
const SOURCE_STYLE = `margin:0 0 8pt;font-family:${UI_FONT};font-size:9.5pt;line-height:1.45;color:${INK};`;
const RULE_STYLE = `border:0;border-top:1pt solid ${RULE};margin:14pt 0;`;
const PLAN_LIST_STYLE = `margin:0 0 10pt;padding-left:22pt;font-family:${UI_FONT};font-size:10pt;color:${INK};`;

// Per-tag styles applied to the HTML that `marked` produces for an answer body.
const MD_STYLES = {
  p: `margin:0 0 8pt;font-family:${BODY_FONT};font-size:11pt;line-height:1.45;color:${INK};`,
  ul: `margin:0 0 8pt;padding-left:22pt;font-family:${BODY_FONT};font-size:11pt;color:${INK};`,
  ol: `margin:0 0 8pt;padding-left:22pt;font-family:${BODY_FONT};font-size:11pt;color:${INK};`,
  li: 'margin:0 0 3pt;line-height:1.45;',
  h1: `margin:14pt 0 6pt;font-family:${UI_FONT};font-size:14pt;font-weight:bold;line-height:1.3;color:${INK};`,
  h2: `margin:14pt 0 6pt;font-family:${UI_FONT};font-size:12.5pt;font-weight:bold;line-height:1.3;color:${INK};`,
  h3: `margin:12pt 0 5pt;font-family:${UI_FONT};font-size:11.5pt;font-weight:bold;line-height:1.3;color:${INK};`,
  h4: `margin:12pt 0 5pt;font-family:${UI_FONT};font-size:11pt;font-weight:bold;line-height:1.3;color:${INK};`,
  h5: `margin:10pt 0 4pt;font-family:${UI_FONT};font-size:10.5pt;font-weight:bold;color:${INK};`,
  h6: `margin:10pt 0 4pt;font-family:${UI_FONT};font-size:10pt;font-weight:bold;color:${MUTED};`,
  blockquote: `margin:0 0 8pt;padding-left:10pt;border-left:2pt solid ${RULE};font-family:${BODY_FONT};font-size:11pt;font-style:italic;color:${MUTED};`,
  pre: `margin:0 0 8pt;padding:6pt 8pt;background:#f6f8fa;border:1pt solid ${RULE};font-family:${MONO_FONT};font-size:9pt;white-space:pre-wrap;`,
  table: `border-collapse:collapse;margin:0 0 10pt;font-family:${UI_FONT};font-size:9.5pt;color:${INK};`,
  th: `border:1pt solid ${RULE};padding:4pt 6pt;background:#f0f3f6;text-align:left;font-weight:bold;`,
  td: `border:1pt solid ${RULE};padding:4pt 6pt;vertical-align:top;`,
  a: `color:${LINK};text-decoration:underline;`,
  hr: RULE_STYLE,
};

const CODE_INLINE_STYLE = `font-family:${MONO_FONT};font-size:9pt;background:#f6f8fa;`;
const CODE_BLOCK_STYLE = `font-family:${MONO_FONT};font-size:9pt;`;
// A quoted paragraph must keep the blockquote's muted italic voice rather than
// resetting to body colour, which the generic <p> rule would otherwise do.
const QUOTE_PARA_STYLE = `margin:0 0 6pt;font-family:${BODY_FONT};font-size:11pt;line-height:1.45;font-style:italic;color:${MUTED};`;

// ── Helpers ───────────────────────────────────────────────────────

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Remove <think>/<thinking> reasoning blocks, including an unterminated trailing
 * one left behind by an interrupted stream. Shared with the message renderer so
 * the copy matches exactly what is on screen.
 */
export function stripThinking(content) {
  if (!content) return '';
  return content
    .replace(/<(think|thinking)>([\s\S]*?)<\/\1>/gi, '')
    .replace(/<(think|thinking)>([\s\S]*)$/i, '')
    .trim();
}

function formatTime(isoDate) {
  if (!isoDate) return '';
  const d = new Date(isoDate);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

/** Markdown → HTML with a style attribute inlined on every element. */
function markdownToStyledHtml(markdown) {
  const raw = marked.parse(markdown, { async: false, gfm: true });
  const clean = DOMPurify.sanitize(raw);
  const doc = new DOMParser().parseFromString(`<body>${clean}</body>`, 'text/html');

  doc.body.querySelectorAll('*').forEach(el => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'code') {
      el.setAttribute('style', el.parentElement?.tagName === 'PRE' ? CODE_BLOCK_STYLE : CODE_INLINE_STYLE);
      return;
    }
    if (tag === 'p' && el.parentElement?.tagName === 'BLOCKQUOTE') {
      el.setAttribute('style', QUOTE_PARA_STYLE);
      return;
    }
    const style = MD_STYLES[tag];
    if (style) el.setAttribute('style', style);
    if (tag === 'table') {
      // Word reads these presentational attributes more reliably than CSS borders.
      el.setAttribute('border', '1');
      el.setAttribute('cellspacing', '0');
      el.setAttribute('cellpadding', '4');
    }
    if (tag === 'a') {
      el.setAttribute('target', '_blank');
      el.setAttribute('rel', 'noopener noreferrer');
    }
  });

  return doc.body.innerHTML;
}

/** Plain user-typed text → paragraphs, preserving line breaks. */
function plainTextToHtml(text, style) {
  return String(text ?? '')
    .split(/\n{2,}/)
    .filter(block => block.trim())
    .map(block => `<p style="${style}">${esc(block.trim()).replace(/\n/g, '<br>')}</p>`)
    .join('');
}

function sourceMetaParts(source) {
  const extent = Array.isArray(source.extent) ? source.extent.join(', ') : '';
  return [source.kind, source.sub, source.year, source.meta, extent, source.cite].filter(Boolean);
}

function renderSources(sources) {
  if (!sources?.length) return { html: '', text: '' };

  const rows = sources.map(s => {
    const number = s.n ?? '•';
    const meta = sourceMetaParts(s).join(' · ');
    const lines = [
      `<span style="font-weight:bold">[${esc(number)}]</span> <span style="font-weight:bold">${esc(s.title || s.cite || 'Untitled source')}</span>`,
    ];
    if (meta) lines.push(`<span style="color:${MUTED}">${esc(meta)}</span>`);
    if (s.url) lines.push(`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer" style="${MD_STYLES.a}">${esc(s.url)}</a>`);
    if (s.video?.url) {
      const label = s.video.clip_start ? `Video from ${s.video.clip_start}` : 'Video';
      lines.push(
        `<a href="${esc(s.video.url)}" target="_blank" rel="noopener noreferrer" style="${MD_STYLES.a}">${esc(label)}</a>`
      );
    }
    const textLines = [`[${number}] ${s.title || s.cite || 'Untitled source'}`];
    if (meta) textLines.push(`    ${meta}`);
    if (s.url) textLines.push(`    ${s.url}`);
    if (s.video?.url) textLines.push(`    ${s.video.clip_start ? `Video from ${s.video.clip_start}: ` : 'Video: '}${s.video.url}`);

    return {
      html: `<p style="${SOURCE_STYLE}">${lines.join('<br>')}</p>`,
      text: textLines.join('\n'),
    };
  });

  return {
    html: `<p style="${LABEL_STYLE}">Sources</p>${rows.map(r => r.html).join('')}`,
    text: `Sources\n${rows.map(r => r.text).join('\n')}`,
  };
}

function renderPlan(plan) {
  const steps = Array.isArray(plan?.steps) ? plan.steps.filter(s => s && s.title) : [];
  if (!steps.length && !plan?.scope_note) return { html: '', text: '' };

  const parts = [`<p style="${LABEL_STYLE}">Approved research plan</p>`];
  const textParts = ['Approved research plan'];

  if (plan.scope_note) {
    parts.push(`<p style="${META_STYLE}">${esc(plan.scope_note)}</p>`);
    textParts.push(plan.scope_note);
  }
  if (steps.length) {
    const items = steps
      .map(step => {
        const detail = step.detail ? `<br><span style="color:${MUTED}">${esc(step.detail)}</span>` : '';
        return `<li style="${MD_STYLES.li}">${esc(step.title)}${detail}</li>`;
      })
      .join('');
    parts.push(`<ol style="${PLAN_LIST_STYLE}">${items}</ol>`);
    steps.forEach((step, i) => {
      textParts.push(`${i + 1}. ${step.title}${step.detail ? ` — ${step.detail}` : ''}`);
    });
  }

  return { html: parts.join(''), text: textParts.join('\n') };
}

// ── Public API ────────────────────────────────────────────────────

/**
 * Build the clipboard payload for a whole conversation.
 *
 * @param {object}   opts
 * @param {Array}    opts.messages   Chat messages (tool messages are skipped).
 * @param {string}   [opts.title]    Thread title.
 * @param {string}   [opts.botName]  Bot display name, used to label answers.
 * @param {string}   [opts.userName] Signed-in user, shown in the header.
 * @returns {{html: string, bodyHtml: string, text: string}}
 */
export function buildConversationExport({ messages = [], title, botName = 'AILA', userName } = {}) {
  const threadTitle = title?.trim() || 'Research thread';
  const exportedAt = new Date().toLocaleString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const headerBits = [botName, `Exported ${exportedAt}`, userName].filter(Boolean);

  const htmlParts = [
    `<h1 style="margin:0 0 4pt;font-family:${UI_FONT};font-size:16pt;font-weight:bold;color:${INK};">${esc(threadTitle)}</h1>`,
    `<p style="${META_STYLE}">${esc(headerBits.join(' · '))}</p>`,
    `<hr style="${RULE_STYLE}">`,
  ];
  const textParts = [threadTitle, headerBits.join(' · '), '='.repeat(60), ''];

  const turns = messages.filter(m => m && m.role !== 'tool');

  turns.forEach((msg, idx) => {
    const time = formatTime(msg.created_at || msg.at);

    if (msg.role === 'user') {
      const label = time ? `Question · ${time}` : 'Question';
      htmlParts.push(`<p style="${LABEL_STYLE}">${esc(label)}</p>`);
      htmlParts.push(plainTextToHtml(msg.content, QUESTION_STYLE));
      textParts.push(label.toUpperCase(), String(msg.content ?? '').trim(), '');
      return;
    }

    const content = stripThinking(msg.content);
    const plan = renderPlan(msg.research_plan);
    const sources = renderSources(msg.sources);
    if (!content && !plan.html && !sources.html) return;

    const label = time ? `${botName} · ${time}` : botName;
    htmlParts.push(`<p style="${LABEL_STYLE}">${esc(label)}</p>`);
    textParts.push(label.toUpperCase());

    if (plan.html) {
      htmlParts.push(plan.html);
      textParts.push(plan.text, '');
    }
    if (content) {
      htmlParts.push(markdownToStyledHtml(content));
      textParts.push(content, '');
    }
    if (sources.html) {
      htmlParts.push(sources.html);
      textParts.push(sources.text, '');
    }

    // Rule between turns, but not after the last one.
    if (idx < turns.length - 1) {
      htmlParts.push(`<hr style="${RULE_STYLE}">`);
      textParts.push('-'.repeat(60), '');
    }
  });

  const bodyHtml = `<div style="font-family:${UI_FONT};font-size:11pt;color:${INK};">${htmlParts.join('')}</div>`;
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(threadTitle)}</title></head><body>${bodyHtml}</body></html>`;

  return { html, bodyHtml, text: textParts.join('\n').replace(/\n{3,}/g, '\n\n').trim() };
}

/**
 * Write both clipboard flavours, falling back for browsers without the async
 * clipboard API. The execCommand path still preserves rich formatting, so a
 * Word paste keeps its styling; only the last resort drops to plain text.
 */
async function writeRichText(html, bodyHtml, text) {
  if (navigator.clipboard?.write && typeof ClipboardItem !== 'undefined') {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([text], { type: 'text/plain' }),
        }),
      ]);
      return true;
    } catch {
      // Permission denied or unsupported flavour — fall through.
    }
  }

  try {
    const holder = document.createElement('div');
    holder.setAttribute('contenteditable', 'true');
    holder.innerHTML = bodyHtml;
    holder.style.cssText = 'position:fixed;left:-9999px;top:0;white-space:normal;opacity:0;';
    document.body.appendChild(holder);

    const range = document.createRange();
    range.selectNodeContents(holder);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);

    const ok = document.execCommand('copy');
    selection.removeAllRanges();
    document.body.removeChild(holder);
    if (ok) return true;
  } catch {
    // Fall through to plain text.
  }

  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Copy an entire conversation — questions, answers and source citations — to the
 * clipboard as rich text. Resolves true on success.
 */
export async function copyConversation(opts) {
  const { html, bodyHtml, text } = buildConversationExport(opts);
  return writeRichText(html, bodyHtml, text);
}
