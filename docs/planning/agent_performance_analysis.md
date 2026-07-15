# Agent Performance Analysis Prompt

Use this prompt to generate a comparative performance table across multiple LLM runs from the LexChat agent logs.

---

## Prompt

Analyse the LexChat agent logs and produce a comparative performance table across all research query runs found in the logs.

**Log location:** `server_py/logs/agent.log` (and dated rotations like `agent.log.2026-04-15`)

**What constitutes a "run":** Each run begins with a `[Worker] Starting research on:` line and ends when the Manager produces its final response (the last `ChatLoop Sending request` or `OpenRouter Sending request` with `tools=1` before no further tool calls occur).

**For each run, extract the following metrics:**

| Metric | How to find it |
|---|---|
| Timestamp | Time of `[Worker] Starting research on:` |
| Provider | `[ChatLoop]` = Ollama, `[OpenRouter]` = OpenRouter |
| Model | From `model=...` in the sending request log line |
| Summarise concurrency | From `[ProviderFactory] Created summarise semaphore for ... (concurrency=N)` |
| Phase 1 LEX calls | Count of `[Worker Tool Exec] search_legislation` lines (not `search_legislation_sections`) |
| Phase 1 summarisations | Count of `summarising for query focus` lines that immediately follow Phase 1 calls |
| Phase 2 LEX calls | Count of `[Worker Tool Exec] search_legislation_sections` lines |
| Phase 2 summarisations | Count of `summarising for query focus` lines that follow Phase 2 calls |
| Summarisation failures | Count of `[Summarise] Chunk failed` or `Single-chunk summarisation failed` lines |
| Duplicate legislation_id calls | Whether the same `legislation_id` appears more than once across all `search_legislation_sections` calls |
| Total LEX API calls | Phase 1 + Phase 2 + any `get_legislation_text` calls |
| Total summarisations | All `summarising` lines across the run |
| Context at Worker synthesis | The `~N chars` value from the final Worker `ChatLoop`/`OpenRouter` sending line before the tool count drops to the Manager level (tools=1) |
| Total time | From Worker start to the final Manager `ChatLoop`/`OpenRouter` sending line |

**Notes on log format:**
- Ollama runs use `[ChatLoop]` prefix; OpenRouter runs use `[OpenRouter]` prefix
- A `tools=1` request is the Manager composing its final answer; `tools=3` is the Worker reasoning
- `[Worker Tool Exec]` lines appear for both providers — they share the same tool execution layer
- Summarisation for a run may be interleaved — a `[Summarise] Chunk failed` warning means the raw text was used as fallback, which inflates context size
- If a result was truncated (`Tool result from '...' truncated`), note it — it indicates a summarisation failure caused an oversized raw result

**Output format:**

Produce a markdown table with one column per run, ordered chronologically. Include a notes row at the bottom for anything notable (failures, duplicates, model instruction-following quality). After the table, write a short paragraph summarising the key trend across the runs.

**Example of what good output looks like:**

| | Run 1 | Run 2 | ... |
|---|---|---|---|
| **Timestamp** | 09:34 | 09:48 | ... |
| **Provider** | Ollama | Ollama | ... |
| **Model** | Mistral Large | Mistral Large | ... |
| **Summarise concurrency** | 1 | 1 | ... |
| **Phase 1 LEX calls** | 8 | 7 | ... |
| **Phase 1 summarisations** | 0 | 0 | ... |
| **Phase 2 LEX calls** | 16 | 12 | ... |
| **Phase 2 summarisations** | 15 | 9 | ... |
| **Summarisation failures** | 0 | 0 | ... |
| **Duplicate legislation_id calls** | Yes (5+) | Yes (4+) | ... |
| **Total LEX API calls** | 24 | 19 | ... |
| **Total summarisations** | 15 | 9 | ... |
| **Context at Worker synthesis** | ~110K chars | ~75K chars | ... |
| **Total time** | ~10 min | ~9 min | ... |
| **Notes** | Multiple calls per Act | — | ... |
