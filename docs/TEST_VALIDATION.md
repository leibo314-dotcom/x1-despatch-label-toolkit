# Test version validation

Branch: `agent/colour-mismatch-warning`. Production master remains
`c3c485860debdf9b5ee7816061b2d6c937c314c6`.

Run automated checks with `python -m pytest -q`. To include the supplied real
document, set `X1_SAMPLE_50936` to its local filename. Customer PDFs are not
committed. 26 checks passed with the actual 12-page, 10-item Assembly input.

The complete upload/result workflow was tested in headless Edge at desktop and
390px mobile width, including concurrent separate worker processes, persisted
result reload and download availability. No JavaScript errors or horizontal
overflow. Actual results: docket available; colour requires manual review for
generic finishes; width 10 passed, zero mismatches or unreadable items.

Before the docket bug fix, Schedule 50330 (two pages) and Assembly 50936 (one
page) produced exactly the same page text and rendered pixels as the old code.
Visual review then found a pre-existing Assembly bug: inline screw notation
`#2` created an extra item 2. The Assembly parser now requires a line-leading
item heading, and reads the explicitly labelled Frame instead of glass text.
50936 now generates exactly 10 items. This is a delivery-only change; neither
checking module is used to generate docket pages.

The width rules are a candidate supported by one quote, not independently
validated manufacturing tolerances. 0.01 mm is comparison precision, not a
manufacturing acceptance tolerance. 204/328 are system deductions, not actual
gaps. Review further historical jobs before expanding scope or production use.

The private Blob repository is covered by mocked cross-instance round-trip and
upload tests; actual preview deployment verification is recorded separately.
