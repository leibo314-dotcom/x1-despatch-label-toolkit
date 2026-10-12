# Cat theme assets

The Maine Coon clips were generated for this project with LTX using the same cat reference; they are generated motion, not a claim of stock wildlife footage. All deployed assets are local to `public/cat-theme/`; there are no external media calls.

- Walk: source `cloud-ltx-01`, zero-based frames 4–71, 68 frames at 24 fps. The left-facing version is an offline horizontal mirror. Direction changes only outside the viewport.
- Greeting: source `cloud-ltx-action-03`, all 73 frames at 24 fps. Alpha was keyed from the green background, preserving the native timing. Its source canvas has tail clipping, so the complete clip is restricted to screen-edge entry, with at least a 12 px offscreen margin. It is never played in the middle of the page.
- Audio: the greeting's own 0.8–1.5 s meow, with short fades and reduced volume. It stays muted until the user enables sound. The cue is tied to the greeting's video time.
- Poster: one directly extracted transparent frame from the deployed walk video; used for reduced motion or unsupported/failed playback.

Playback uses measured source displacement and video time, pauses on hidden pages, and reserves an empty corridor clear of the cards, controls, and avatar. Alpha support is checked before showing video. The theme does not subscribe to or change upload, PDF, job, or download logic. Existing themes and generation feedback are retained.
