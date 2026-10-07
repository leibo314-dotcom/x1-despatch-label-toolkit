"""Label-owned X1 extraction. Frozen from a9aaef9 geometry, independent of delivery.
Changes here never alter the delivery parser, renderer, work files or state.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List
import pdfplumber
import pymupdf as fitz
from PIL import Image
DPI = 300

@dataclass
class Item:
    no: int
    desc: str
    colour: str
    frame: str
    suite: str
    flashing: str
    wanz: str
    kg: str
    page_index: int
    header_top: float
    header_bottom: float
    section_bottom: float


def clean_desc(desc: str) -> str:
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc


def detect_document_type(pdf_path: Path) -> str:
    with pdfplumber.open(str(pdf_path)) as pdf:
        if not pdf.pages:
            raise ValueError("The uploaded PDF has no pages.")
        first_page_text = pdf.pages[0].extract_text() or ""

    if re.search(r"\b(?:Short\s+)?Assembly\s+(?:(?:Short|Medium)\s+)?Drawing", first_page_text, re.IGNORECASE):
        return "assembly"
    if re.search(r"(?:^|\n)\s*Schedule(?:\s|$)", first_page_text, re.IGNORECASE):
        return "schedule"
    raise ValueError("Unsupported PDF. Upload an X1 Schedule or Assembly (Short or Detail) PDF.")


def item_heading_words(words: List[dict], page_width: float) -> List[dict]:
    """Find the leading number in an item heading, not references in prose."""
    headings = []
    for word in words:
        if not re.fullmatch(r"#\d+", word['text']) or word['x0'] < page_width * .30:
            continue
        line = [other for other in words if abs(other['top'] - word['top']) < 2]
        if any(other['x0'] < word['x0'] for other in line):
            continue
        # X1 places Quantity directly beneath the boxed item heading.
        if not any(other['text'] == 'Quantity:'
                   and 0 < other['top'] - word['top'] < 25
                   and other['x0'] >= word['x0'] for other in words):
            continue
        headings.append(word)
    return sorted(headings, key=lambda word: word['top'])


def dark_mask(im: Image.Image):
    gray = im.convert('L')
    import numpy as np
    arr = np.array(gray)
    return arr < 200


def trim_diagram(crop: Image.Image) -> Image.Image:
    import numpy as np
    mask = dark_mask(crop)
    h, w = mask.shape
    row_counts = mask.sum(axis=1)
    nz = np.where(row_counts > 2)[0]
    if len(nz) == 0:
        return crop

    top = max(int(nz[0]) - 6, 0)

    # Sundry/summary text is excluded before this trim runs, so keep the last
    # visible dimension line instead of stopping at the blank gap below a frame.
    bottom = int(nz[-1])
    bottom = min(bottom + 10, h - 1)

    crop2 = crop.crop((0, top, w, bottom))
    mask2 = dark_mask(crop2)
    if mask2.any():
        h2, w2 = mask2.shape
        separator_rows = []
        for row_idx in range(int(h2 * 0.25), h2):
            row = mask2[row_idx]
            if row.sum() <= w2 * 0.9:
                continue
            xs = np.where(row)[0]
            if len(xs) and xs[0] < 15 and xs[-1] > w2 - 15:
                separator_rows.append(row_idx)
        if separator_rows:
            cut_at = max(separator_rows[0] - 6, 1)
            crop2 = crop2.crop((0, 0, w2, cut_at))
            mask2 = dark_mask(crop2)
    coords = np.argwhere(mask2)
    if len(coords) == 0:
        return crop2
    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0)
    x0 = max(int(x0) - 12, 0)
    x1 = min(int(x1) + 12, crop2.width - 1)
    y0 = max(int(y0) - 12, 0)
    y1 = min(int(y1) + 12, crop2.height - 1)
    return crop2.crop((x0, y0, x1, y1))


def extract_assembly_diagram(doc: fitz.Document, page_index: int) -> Image.Image:
    page = doc.load_page(page_index)
    candidates = []
    for image_info in page.get_images(full=True):
        image_data = doc.extract_image(image_info[0])
        if image_data["width"] >= 500 and image_data["height"] >= 400:
            candidates.append(image_data)
    if not candidates:
        raise ValueError(f"Could not locate the assembly drawing on page {page_index + 1}.")

    image_data = max(candidates, key=lambda data: data["width"] * data["height"])
    source = Image.open(BytesIO(image_data["image"])).convert("RGB")

    import numpy as np

    grayscale = np.array(source.convert("L"))
    coordinates = np.argwhere(grayscale < 245)
    if not len(coordinates):
        raise ValueError(f"The assembly drawing on page {page_index + 1} is blank.")
    y0, x0 = coordinates.min(axis=0)
    y1, x1 = coordinates.max(axis=0)
    content = source.crop((int(x0), int(y0), int(x1) + 1, int(y1) + 1))

    # Keep the original Assembly resolution for the small printed diagram.
    padded = Image.new("RGB", (content.width + 24, content.height + 24), "white")
    padded.paste(content, (12, 12))
    return padded



def extract_diagram_images(
    pdf_path: Path,
    items: List[Item],
    out_dir: Path,
    document_type: str = "schedule",
) -> Dict[int, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(str(pdf_path)) as pdf, fitz.open(str(pdf_path)) as doc:
        scale = DPI / 72.0
        result: Dict[int, Path] = {}
        page_items: Dict[int, List[Item]] = {}
        for item in items:
            page_items.setdefault(item.page_index, []).append(item)
        for pidx, page in enumerate(pdf.pages):
            if pidx not in page_items:
                continue
            if document_type == "assembly":
                for item in page_items[pidx]:
                    out_path = out_dir / f"diagram_{item.no}.png"
                    extract_assembly_diagram(doc, item.page_index).save(out_path)
                    result[item.no] = out_path
                continue

            fpage = doc.load_page(pidx)
            pix = fpage.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            words = page.extract_words(x_tolerance=1, y_tolerance=1)
            for item in page_items[pidx]:
                crop_bottom = item.section_bottom - 5
                for word in words:
                    text = word["text"].strip().lower()
                    if not (item.header_top + 8 < word["top"] < item.section_bottom):
                        continue
                    if text.startswith("sundry") or text == "number":
                        crop_bottom = min(crop_bottom, word["top"] - 4)
                for line in page.lines:
                    width = abs(line["x1"] - line["x0"])
                    if not (item.header_top + 24 < line["top"] < crop_bottom):
                        continue
                    if (
                        width > page.width * 0.75
                        and line["x0"] < page.width * 0.12
                        and line["x1"] > page.width * 0.88
                    ):
                        crop_bottom = min(crop_bottom, line["top"] - 4)
                crop_bottom = max(crop_bottom, item.header_top + 24)

                objs = []
                for obj in list(page.lines) + list(page.rects):
                    x0, x1 = obj['x0'], obj['x1']
                    top, bottom = obj['top'], obj['bottom']
                    if x1 < 230 and top > item.header_top + 8 and bottom < crop_bottom:
                        if abs(x1 - x0) > 300 and abs(bottom - top) < 2:
                            continue
                        objs.append((x0, top, x1, bottom))
                if objs:
                    x0 = min(o[0] for o in objs)
                    y0 = min(o[1] for o in objs)
                    x1 = max(o[2] for o in objs)
                    y1 = max(o[3] for o in objs)
                    chars = []
                    min_char_top = max(item.header_top + 4, y0 - 12)
                    max_char_bottom = min(item.section_bottom - 8, y1 + 14)
                    for ch in page.chars:
                        if ch['x0'] > x0 - 28 and ch['x1'] < min(225, x1 + 22) and ch['top'] >= min_char_top and ch['bottom'] <= max_char_bottom:
                            chars.append(ch)
                    if chars:
                        x0 = min([x0] + [c['x0'] for c in chars])
                        y0 = min([y0] + [c['top'] for c in chars])
                        x1 = max([x1] + [c['x1'] for c in chars])
                        y1 = max([y1] + [c['bottom'] for c in chars])
                    x0 = max(0, x0 - 6)
                    y0 = max(0, y0 - 6)
                    x1 = min(225, x1 + 6)
                    y1 = min(page.height, crop_bottom, y1 + 8)
                    crop = img.crop((int(x0 * scale), int(y0 * scale), int(x1 * scale), int(y1 * scale)))
                    crop = trim_diagram(crop)
                else:
                    x0_pt = 18
                    x1_pt = 225
                    y0_pt = item.header_top + 4
                    y1_pt = crop_bottom
                    crop = img.crop((int(x0_pt * scale), int(y0_pt * scale), int(x1_pt * scale), int(y1_pt * scale)))
                    crop = trim_diagram(crop)
                out_path = out_dir / f"diagram_{item.no}.png"
                crop = trim_diagram(crop)
                crop.save(out_path)
                result[item.no] = out_path
        return result
