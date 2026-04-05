# Phase 2: Human-Friendly Ask Output

**Status:** Code written and tests passing (2026-04-05). Pending manual verification — do not mark fully complete until manual re-verification passes.

---

## Goal

Make ask answers human-readable in Telegram. Phase 1 returns raw file paths and snippets — this phase removes all technical leakage from user-facing output.

---

## Direction

- Format search results as natural language, not raw file-system paths or markdown
- Optionally include a light grounding line such as:
  - "Нашёл в 1 заметке"
  - "Основано на 2 записях"
- No file paths in user-facing output (e.g. `/data/inbox/20260405_...md` must not be shown)
- No raw technical markdown leakage (frontmatter fields, internal headers)
- Output should feel product-like, not developer-like

---

## Implementation Scope

Changes are purely in the bot layer (`src/digital_brain_bot.py`), inside `on_callback()` for the `confirm_ask` branch:
- `SearchResult.snippet` already contains the relevant text excerpt — formatting logic wraps it
- No changes needed to `storage.py` signatures or search logic

---

## Storage Change Needed

None. `MarkdownStorage.search()` already returns `SearchResult(path, score, snippet)`.

---

## Tests to Add

- Assert that the user-facing reply text for an ask result contains no file path patterns (e.g., regex asserting no match for `\/.*\.md`)
- Assert that `SearchResult.snippet` content appears in the reply, not the raw path
- Assert grounding line (e.g. "Нашёл в N заметках") appears when results > 0

---

## Out of Scope for Phase 2

- RAG (retrieval-augmented generation)
- LLM-based answering
- Semantic / embedding-based search
- Streaming responses
