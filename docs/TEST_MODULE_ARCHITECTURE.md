# Test version structure — revised after user feedback

Only `agent/colour-mismatch-warning`; do not update master or Production.

Delivery remains the existing pipeline:

`Upload -> original generate_job -> original renderer -> result -> original download`

`x1_despatch_label_real_diagram.py` is identical to known-working commit a4c68f7.
The generate_job, generate, generate_from_blob and download functions also retain
their original code. No checks, subprocess wrapper, source parser or Blob result
repository is required to produce or download a docket. Previously attempted
Assembly parser fixes were reverted with the rest of the delivery changes.

After the download link is ready, the browser requests the optional checks:

`saved input -> one shared document parse -> colour consistency / TL40 width rules`

The two checking functions are separate modules, with independent exception
handling and no import or call of the delivery pipeline. They share immutable
source facts to avoid parsing twice. Results are cached in checks.json beside
the input. Retry rechecks both; reloading uses the cache. Results appear only
on screen. No check report downloads are exposed.

The result page never runs checks on the server. A check failure, missing OCR
dependency, or missing source leaves the docket download available. The inherited
temporary local job storage has the same lifetime/instance limitations as the
original delivery app; this change does not replace its storage infrastructure.

Colour: one distinct recorded colour -> its name + Pass. Multiple names -> Fail
with collapsed groups; missing colour data -> Needs review. This is a consistency
check, not certification of a manufacturer's finish or chosen coating.

Panel: all supported items match -> Pass. Mismatch -> Fail; missing/unsupported
evidence -> Needs review. Only non-pass results have expandable details. No
manufacturing dimensions, formula or counts appear in the collapsed row.

Rules: single W-204+18*S-20*C; French (W-328+18*S-20*C)/2. V661 is checked
against independently read drawing dimensions. 204/328 are system deductions,
not measured physical gaps. Scope is the verified TL40 families from quote
50936; no height or glass checks. Unequal effective leaves, mixed boundaries,
ambiguous OCR, unsupported systems or incomplete cut lists do not receive Pass.

The old universal 240 mm rule is removed. Actual source quote 50936 has 12 pages,
10 items. Rail lengths: 646,664,682,626,606,636,695,704,626,616 mm. All match.
Further independent historical quotes are needed before expanding the rule set.

Preview dependencies are locked in pyproject.toml / uv.lock. RapidOCR's desktop
OpenCV dependency is explicitly replaced by opencv-python-headless, so the
server does not need X11/libxcb. Use uv sync and uv run app.py for local checks;
run tests with uv run --with pytest python -m pytest -q. requirements.txt remains
the unchanged legacy desktop/delivery dependency list for the existing launchers.
