# Preview themes

- **Simple** is the current compact, centered theme. Its stored key remains
  `standard`, so existing selections continue to work. The original red button
  and its hover/focus/disabled styles are retained. During generation the whole
  upload progress panel is hidden without layout space; the Working button
  provides busy feedback. Error and completion messages remain available without
  a progress bar or percentage. Time-ring cards retain a 10% opaque white fill
  and no blur.
- **Original** restores the visual layout from commit
  `d00de43f78d5a524aa5ebb252d1e3520980c4387`, dated 2026-10-12 08:44:15
  Pacific/Auckland (2026-10-11 19:44:15 UTC). This is the latest test-branch
  commit before the requested 2026-10-12 18:00 NZDT cutoff (05:00 UTC). The next
  theme change was `65a8f09` at 18:37:06 NZDT. The historical CSS was last changed
  at `f49171d` on 2026-10-08 and was still present unchanged in `d00de43`.
- **Lake Tekapo** and **Sakura** keep their existing styles and feedback.

Original restores the large introductory headings, source filename on the result
page, 900px content width, 758px upload card, 70% opaque white fill, 24px blur,
original spacing and responsive rules. These styles are already the shared CSS
base; Original is excluded from the newer centered-layout overrides. Its sole
header adaptation is keeping the theme picker and space for it. The historical
version has no custom background animation or animation script: its generation
feedback is the native progress control, including the browser's indeterminate
animation. Original retains that behavior and never starts Simple's time ring.

This is a presentation selection only. No historical Python code, upload logic,
PDF renderer, output job behavior, checks or storage code is restored. Only the
isolated `agent/colour-mismatch-warning` Preview branch may be deployed.
