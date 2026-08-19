/**
 * Feature flag definitions — label, description, and which tab owns each.
 *
 * `group` is what splits them: 'features' are user-facing capabilities and live
 * on Developer → Configuration; 'caching' are cost/performance internals and
 * live on the Cache tab, beside the metrics they affect. Previously all nine sat
 * on Developer, and the Cache tab had to tell the operator to go elsewhere to
 * switch the thing it was reporting on.
 *
 * NOTE: `drafting_mode_enabled` exists server-side (routers/developer.py) but is
 * deliberately absent here — the drafting bot is unshipped, on its own branch.
 * It is still carried through saves by the spread in the toggle handler.
 */
export const FLAG_DEFS = [
  {
    flag: 'matters_enabled',
    group: 'features',
    label: 'Matters',
    desc: 'Lets users organise threads into named matters with notes.',
  },
  {
    flag: 'research_mode_enabled',
    group: 'features',
    label: 'Research mode',
    desc: 'Offers the "Research" chat mode (deep single-query research via the Worker) in the mode selector.',
  },
  {
    flag: 'deep_research_mode_enabled',
    group: 'features',
    label: 'Deep Research mode',
    desc: 'Offers the "Deep Research" chat mode (editable multi-step research plan) in the mode selector.',
  },
  {
    flag: 'suggested_questions_enabled',
    group: 'features',
    label: 'Suggested question buttons',
    desc: "Renders the assistant's follow-up questions and clarification options as one-click buttons. When off, the assistant writes them into the answer as ordinary text instead.",
  },
  {
    flag: 'session_feedback_enabled',
    group: 'features',
    label: 'Session feedback form',
    desc: 'Shows a "Finished session" button in the chat header that opens the end-of-session feedback form (the pre-pilot questionnaire).',
  },
  {
    flag: 'weekly_survey_enabled',
    group: 'features',
    label: 'Weekly user survey',
    desc: 'Pops up the 6-question productivity survey once a week, and shows a "Take weekly survey" button until it has been completed.',
  },
  {
    flag: 'prompt_caching_enabled',
    group: 'caching',
    label: 'Prompt caching (Anthropic via OpenRouter)',
    desc: 'Marks cache breakpoints on Anthropic models so repeated agent-loop context is billed at the cached rate.',
  },
  {
    flag: 'tool_memo_enabled',
    group: 'caching',
    label: 'Tool-call caching (Deep Research)',
    desc: 'Serves exact repeat tool calls across Deep Research steps from memory instead of re-fetching and re-summarising.',
  },
  {
    flag: 'local_prompt_cache_enabled',
    group: 'caching',
    label: 'Local prompt caching',
    desc: 'Reuses document summaries across users and providers when the same text is researched with the same question — exact match only.',
  },
];

export const flagsInGroup = group => FLAG_DEFS.filter(f => f.group === group);
