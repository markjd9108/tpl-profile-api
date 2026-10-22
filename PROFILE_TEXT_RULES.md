# Profile Text Rules (modular participant profiles)

These rules govern every line of personalised text in a modular profile. The automatic checks in `profile_text_rules.py` enforce the measurable rules. A profile that fails any check is not published.

## 1. Who the reader is
- A working professional, often reading English as a second language.
- They will read the profile once, on their phone, soon after the session.
- The text must be clear, professional and encouraging. It must leave them knowing one thing they do well and one thing to do next.

## 2. Plain, professional English
- One idea per sentence. No sentence longer than 22 words. Aim for 10 to 16.
- Use common words. Prefer "start" to "commence", "check" to "verify".
- No idioms, slang or figures of speech ("take it one step further", "big payoff", "close the loop", "on the same page", "a beat", "land" for a message).
- No informal judgement words ("how good", "pretty", "really", "very", "just", "stuff").
- No colons, semicolons, dashes, brackets or exclamation marks inside text.
- No numbers or digits.
- Professional, warm tone. Write as a respected coach would speak to a senior colleague.

## 3. Structure of every message
- **Praise first.** Open with what the person does well, in specific terms.
- **One shift.** Name one change, not several.
- **A concrete action.** Say what to do and when ("Next time an instruction is unclear, describe what you have in your own words. Then ask the other person if it is correct.").
- **Why it matters.** One short sentence on the benefit at work.
- Link the strength and the growth step to a Clarity Loop step (Clarify, Check or Confirm) by name.

## 4. What the text may be based on
- Only the person's own answers and their blended results.
- Never what a peer said or thought about them. No "others saw you as".
- Never invent behaviour. Every claim must trace to an answer they gave.
- Strengths must be genuine. A middle answer is not a strength. Choose the behaviour that scored highest.

## 5. What the text must not do
- Never state or restate a level, score, band or percentage. The visuals show these.
- Never say which area scored higher or lower.
- Never use the participant's name.
- Never mention games, roles, pieces or activities outside the game cards.
- Never mention feelings outside the emotional journey summary.
- Never use the word "actually".

## 6. Slot by slot

| Slot | Words | Rule |
|---|---|---|
| Hero line | 15 to 35 | Strength, then the next step. Two short sentences. |
| Snapshot paragraph | 45 to 90 | Strength in action, then one action, then the benefit. |
| Strength heading | 3 to 8 | Starts with "You". No full stop. |
| Strength paragraph | 35 to 80 | Praise only. No "but", "however" or "tend to". Names a Clarity Loop step. |
| Growth heading | 3 to 8 | An instruction. No full stop. |
| Growth paragraph | 35 to 80 | Current habit, concrete action, benefit, Clarity Loop step. |
| Result bullets | 10 to 26 each | First bullet a strength, second the biggest opportunity. |
| Area lines | 15 to 42 each | What they do well in that area, then the next step if one is needed. |
| Game cards | 20 to 60 each | What they did in that game, in their role. Credit first. |
| Emotional journey | 45 to 95 | What the feelings show, linked to the behaviour at that moment. Ends with "At work, ..." and one action. |
| Next moves | 20 to 48 each | Manager one-to-one, learning resource, mentor. Each has an action for this week or month. |

## 7. Approved examples
- "You speak up when something is unclear. That is the right instinct. Next time, describe what you have in your own words. Then ask the other person if it is correct."
- "Explains the expected result, including what it must contain, the standard required and the deadline."
- "When you lead, you stay patient, repeat the key details and invite questions."
- "At work, treat rising frustration as a signal. Pause, describe what you have, and confirm it is correct before you continue."

## 8. Rejected examples and why
- "Take it one step further: describe what you have and ask if it matches." Idiom and colon.
- "how good it needs to be" Informal.
- "You keep instructions simple." Not a genuine strength in the answers.
- "You started unsure, felt more pressure in the middle and finished frustrated. This is a normal reaction." Describes feelings without linking them to behaviour or giving an action.

## 9. Maintaining these rules
- Every time a phrase is flagged, add it to `BANNED_PHRASES` in `profile_text_rules.py` and to section 8 here.
- Run the checker on every profile before it is published.
- Review the first profiles of each new workshop by hand before they are sent.
