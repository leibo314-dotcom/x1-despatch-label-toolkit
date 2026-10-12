# Generation animation (Preview only)

Source: the user's Claude artifact [时间之环](https://claude.ai/artifact/AoHqKGq9wmPa3W87RXUg1X),
exported through its normal **Export → HTML** control on 2026-10-12 after the
user signed in. `time-ring-original.html` is the unmodified export. No generated
video, external asset, account connection or audio is needed at runtime.

Although the original canvas label and a comment say ten seconds, its actual
`DUR` is **15 seconds**. That duration, the white background, all seven rings,
150 seeded particles, colours, easing and drawing score are retained.
`public/time-ring.js` contains the original drawing score verbatim; only sizing
and playback ownership have been separated. The original click-to-pause control
and infinite loop are omitted because this is non-interactive background scenery.

The animation is **Simple only** (formerly named Standard). It still requires
`data-theme="standard"` so saved preferences remain compatible. Original, Lake
Tekapo and Sakura do not play the time ring. The initial theme (`tekapo` in
`public/theme.js`) and saved theme preferences are unchanged. Historical dynamic themes (`tekapo-minimal` and
`city-night`) were removed in 8e18d69 and are not restored. On the current baseline,
the old optional `X1Scenery` upload/result hooks remained without an implementation.
Those hooks now control this score. Internal upload progress tracking remains.
Simple hides the entire upload status panel and its layout space while busy,
including when motion is reduced. The existing Working button indicates activity;
errors remain visible after the form is restored, without a bar or percentage.
Other themes retain their existing progress feedback. While the score is active,
Simple cards use a 10% opaque white fill with no backdrop blur. All themes keep
the original red upload button, including its hover, focus and disabled styles.

One validated submit starts one clock. The result page resumes the same elapsed
time, rather than starting again. A score already finished during upload stays
finished. A result-page reload can only resume the remaining time for that same
job. Direct result visits do not start an animation. Each genuine output retry
can start one new score; re-entrant upload/retry clicks cannot duplicate requests.
Failure, theme change, reduced-motion preference and back/forward cache restore
clean up playback. Blocked storage disables cross-page continuation rather than
replaying. Missing canvas support leaves the form and PDF pipeline usable.

Successful generation exposes the PDF downloads immediately, even if the score
is still finishing. No renderer, server route, PDF content, storage format, or
output dependency changes. The canvas ignores pointer input, sits behind controls,
is hidden from assistive technology, and is excluded from browser printing.

Only branch `agent/colour-mismatch-warning` may be published to Preview. Never
push this work to `master` or promote a deployment to Production. The baseline
705a881 and 81194ef result-page layout changes are retained.

## Checks

- `node --test tests/*.test.js` covers the clock, navigation/resume, one-shot end,
  retries, invalid uploads, duplicate submits, failure cleanup, theme isolation,
  reduced motion, unavailable storage/canvas, and preserved drawing source.
- Existing Python tests cover independent outputs, document extraction and PDF
  label geometry. Real delivery output is additionally compared to the unchanged
  baseline by extracted text and rendered page pixels during this change.

The follow-up Simple/Original theme checks cover persistence of the former
Standard preference, storage failures, Original's exclusion from the time ring,
the entire hidden Simple progress panel (zero layout height), error/ready text
without orphan percentages, and unchanged Tekapo/Sakura feedback. Original's
desktop content geometry, fill, blur and type sizes match a rendered `d00de43`
reference. See `THEMES.md` for the historical source and scope.

Verified for this change: 15 JavaScript tests passed; 40 Python tests passed and
3 optional real-sample tests skipped. A real Schedule produced five docket pages
with identical extracted text and per-page rendered pixels before/after. Browser
visual QA confirmed Standard's drawing behind controls and clean switches to
Tekapo/Sakura using a local preview without any upload. Full browser upload QA
remains unverified: the local upload request was not approved and the Chrome
extension reported that local-file access was not enabled. No permissions were
changed and that upload was not retried through another mechanism.
