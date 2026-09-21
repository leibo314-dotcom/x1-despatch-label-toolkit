# Test site: independent document tools

Scope: `agent/colour-mismatch-warning` only. Do not merge, push to master, or
promote a deployment to Production as part of this change.

## Design before implementation

One upload accepts related Schedule / Assembly Detail / itemised BOM PDFs.
The upload service validates files and stores an immutable input manifest. It
does not generate a docket or decide check results.

The results page starts three separate HTTP requests:

```
Upload -> job/input manifest
           |-- delivery service -> own work directory, result.json, docket PDF
           |-- colour service   -> own work directory, result.json, report
           `-- width service    -> own work directory, result.json, report
```

Each service is lazy-loaded, reads the original inputs, and owns its result and
artifacts. Services never import one another. The shared document reader only
extracts facts; it contains no manufacturing rules. Delivery retains the existing
renderer, without introducing check dependencies into it. Check results never
become docket pages. Refreshing results reads persisted results, rather than
rerunning calculations. Retry addresses one service only. Exceptions are visible
in that service's card; no check gates the docket or another check. Separate
requests and fresh subprocesses isolate feature exceptions, native crashes and
timeouts (150 seconds per calculation). Storage loss or host resource exhaustion
remain shared infrastructure failures; these are not separate compute containers.

Local runs use atomic filesystem writes. Preview runs use private Vercel Blob
under the separate `x1-test-jobs` prefix. Inputs, results and docket artifacts can
be read across instances; mutable result reads bypass the CDN cache. Each run
uses a fresh temporary working directory. A Delete button removes that job's
inputs and artifacts. No automatic retention expiry is currently configured.

## Width rule boundaries

Deterministic arithmetic, Decimal millimetres; no LLM calculation. OCR reads only
dimensions in embedded X1 drawing images. Reject low-confidence, inconsistent,
or unsupported evidence. Never infer a width from actual V661: that would make a
wrong rail validate itself. Profile-table columns identify actual lengths and
quantities, not the largest number anywhere in a line.

Initial family: TL40, V650/V651, V661, one single or one compensated equal-leaf
French door group, zero to two integrated or coupled neighbours. V662 and V700/V246
have different rules. Mixed neighbour families, unequal effective French leaves,
multiple door groups, top lights, ambiguous section mapping, missing itemised
BOM, and unrecognised layouts must not receive a pass.

Single: W - 204 + 18*S - 20*C.
French: (W - 328 + 18*S - 20*C)/2.
204/328 are total system deductions, not physical gaps. No height or glass checks.
The old universal 240 mm frame/rail rule is removed, not run alongside these.

## Evidence review

50936 has 12 PDF pages for 10 items (continuation pages at 6 and 12). The drawing
dimensions are raster images. Actual V661 lengths for items 1-10 are
646, 664, 682, 626, 606, 636, 695, 704, 626, 616 mm.
Door widths are 850 for items 1-5, then 1600, 1700, 1700, 1600, 1600.
All ten examples agree arithmetically with the supplied candidate rules.
This is validation against one quote, not independent manufacturer certification.

French drawing partitions need boundary compensation: item 7 is 859+841
(right sidelight adds 18); item 9 is 810+790 (left coupling subtracts 20).
The effective leaf widths are equal in each case. Arbitrary unequal leaves are
outside this initial rule family. Profile quantities are cross-checked against
the drawing and unit quantity, never treated as neighbour counts blindly.

The brief's example summary counts mix checked and unsupported totals. Use
mutually exclusive item counts: total = passed + mismatch + manual + unsupported.
No matching-item warnings; keep full evidence in the downloadable JSON report.
Generic colours such as '1 of Standard 2 Colours' are unresolved colour data,
not proof that all actual finishes match. Multiple concrete colours are a review
flag, not proof the job was specified incorrectly.

## Verification plan

Rule tests: all ten examples, positive/negative differences, unsupported systems,
missing data, unequal leaves, and multiple actual rail lengths.
Reader tests: item continuation, column parsing, raster dimensions, confidence,
quantity and topology consistency, and duplicate/conflicting source documents.
Workflow tests: each service fails independently; check-only results remain
available after delivery failure; no calculation on result GET; retries do not
overwrite sibling artifacts; local and Blob upload use the same dispatcher.
Regression: compare docket output with baseline on Schedule and Assembly PDFs.
Visual review: upload/results pages and the generated docket.
