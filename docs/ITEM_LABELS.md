# Avery item labels (Test only)

The test UI saves one upload, then starts two independent requests:

* `outputs/docket` calls the unchanged delivery renderer.
* `outputs/labels` calls `features/item_labels`, with its own parser, drawing
  extraction, renderer, scratch folder, status, retry and download.

Neither output imports or calls the other generator. The label extraction
geometry was copied from commit a9aaef9 into a label-owned module; later label
changes cannot alter delivery. A failed output never deletes the shared input
or the other PDF. The optional colour check remains a separate request. The
panel width / gap feature has been removed from both UI and check execution;
its older source modules remain inactive for possible future restoration.
Existing clients
without `independent_outputs` retain the original synchronous delivery flow.

New independent jobs keep their input and PDFs under random job IDs in private
Blob storage when configured, with a local cache. This lets concurrent requests
and downloads use different server instances. Each output is written atomically
and recovered separately. Without Blob, jobs use the original local temporary
storage. Private job storage has no automatic expiry policy configured here.

## Physical template

Authority: user-supplied `Avery_L7173_Word_Template.doc`, read through Word and
its exported PDF; no guessed vendor margins. Two columns, five rows.

* A4 PDF: 210 × 297 mm, portrait; PrintScaling=None.
* Label width: 5616 twips = 280.8 pt = 99.06 mm.
* Label height: 3231 twips = 161.55 pt = 56.99125 mm.
* Column starts from the left: 13.25 pt and 301.25 pt.
* Row starts from the top: 17.10, 178.70, 340.25, 501.85, 663.40 pt.
* Across first, then down; item 11 starts the next A4 sheet. Unused slots blank.
* The Word outlines have 8.5 pt rounded corners. All ink, including the blue
  header, stays at least 2 mm inside the die-cut boundary. A uniform scale fits
  the entire original layout within this inset; no text is cut off to fit.
* Item and Desc use bold for both the field name and complete value. Wrapping
  and shrinking measure the actual bold font. Output v3 avoids old PDF caches.

The dimensions and positions come from the label outlines in the rendered
template, which differ from Word's text margins. No extra page title, footer,
cutting marks or page-number area shifts the labels. Print at 100% / Actual size.

The approved reference's blue header, original LIDAR logo, Quote, Item, Desc,
and right-side drawing are retained. Colour, Suite, Flash and WAN are omitted.
Only the logo region of
the supplied reference bitmap is shown through a PDF clip. Item data and Quote
are searchable PDF text. Item uses a 17.5 pt maximum and Desc uses a 16.7 pt
maximum before the safety inset scale. The description uses hanging lines in
a fixed 64 pt tall area, reserving at least one additional blank line below
the text even when shrinking longer descriptions. No ellipses or dropped
words. One physical item means one label, regardless of Quantity. Schedule,
Assembly Drawing (Short) and Assembly Medium Drawing (Details) use the same
independent label output route.

## Verification

Tests cover Schedule and Assembly extraction, 11 items across two sheets,
template coordinates, full long text, private storage across server instances,
and both directions of output failure. Visual QA includes a real 18-item
Schedule and a 50364-style example. Real delivery output is compared by text
and rendered pixels with the pre-change renderer output.
