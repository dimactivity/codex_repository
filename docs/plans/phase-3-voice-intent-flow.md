# Phase 3: Voice → Intent Flow

**Status:** NOT implemented. Planned after Phase 1 is stable and voice UX direction is validated.

---

## Goal

Apply the same intent-first confirmation flow to voice messages. Voice must not be auto-assumed to be a capture — it must go through `classify_intent()` on the transcript first.

---

## Direction

- One voice message = one input unit (same as text)
- Flow: transcribe → `classify_intent(transcript)` → confirmation buttons → user confirms → execute
- Voice is NOT automatically assumed to be capture
- If intent is confident (capture or ask): show 2-button confirmation (same as text flow)
- If intent is unclear: show 3-button clarification (same as text flow)
- Cancel and reset behavior: identical to text flow

---

## Architecture Note

Phase 1 intentionally designed `on_callback()` to be voice-agnostic — it reads from `context.user_data` regardless of how the pending state was set. Phase 3 only needs to change `on_voice()`:

```
on_voice()  →  transcribe  →  classify_intent(transcript)
            →  store pending_text / pending_intent / pending_message_id
            →  send confirmation buttons
```

`on_callback()` requires **no changes** — it handles the button press identically.

---

## Source Field

Continue using `"telegram_voice_transcript"` as the `source` parameter when calling `save_capture()`, so audit logs distinguish voice-originated captures from text ones.

---

## Key Constraint

The current `on_voice()` skips intent detection entirely and routes directly to `save_capture()`. This must change in Phase 3 — the direct-save path is replaced with the same pending-state + button flow used for text.

---

## Tests to Add

- Mock transcription → `classify_intent()` called on transcript → confirmation buttons shown
- Mock confirm_capture callback after voice → `save_capture()` called with `source="telegram_voice_transcript"`
- Mock confirm_ask callback after voice → `search()` called
- Stale button behavior for voice-originated pending state (identical to text stale tests)

---

## Out of Scope for Phase 3

- LLM-based transcription improvement
- Multilingual voice support
- Background / continuous recording
- Voice-specific UI or formatting differences from text flow
