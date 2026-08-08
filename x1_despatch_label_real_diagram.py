#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple

import pdfplumber
import fitz
from PIL import Image
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

DPI = 220

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


@dataclass
class HeaderMeta:
    quote_no: str
    title: str
    company_name: str
    job_description: str
    printed: str
    address: str
    number_of_units: str


def clean_desc(desc: str) -> str:
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc


def looks_like_address(line: str) -> bool:
    normalized = re.sub(r"\s+", " ", line).strip()
    if not normalized or not re.search(r"\d", normalized):
        return False
    street_suffixes = (
        "rd", "road", "st", "street", "ave", "avenue", "dr", "drive",
        "ln", "lane", "ct", "court", "way", "pl", "place", "cres",
        "crescent", "terrace", "tce", "highway", "hwy",
    )
    return bool(
        re.search(
            rf"\b(?:{'|'.join(street_suffixes)})\.?\b",
            normalized,
            re.IGNORECASE,
        )
    )


def parse_header_meta(first_page_text: str) -> HeaderMeta:
    quote_no = ""
    m = re.search(r"Quote\s+No\.\s*(\d+)", first_page_text)
    if m:
        quote_no = m.group(1)
    printed = ""
    m = re.search(r"Printed:\s*(\d{2}/\d{2}/\d{4})", first_page_text)
    if m:
        printed = m.group(1)
    lines = [ln.strip() for ln in first_page_text.splitlines() if ln.strip()]
    title = next(
        (ln for ln in lines if re.fullmatch(r"[A-Z]{1,6}\d{3,}[A-Z0-9]*", ln)),
        "",
    )
    address = ""
    for ln in lines:
        if looks_like_address(ln):
            address = ln
            break
    return HeaderMeta(
        quote_no=quote_no,
        title=title,
        company_name="",
        job_description=title,
        printed=printed,
        address=address,
        number_of_units="",
    )


def group_words_by_line(words: List[dict], y_tolerance: float = 3.0) -> List[List[dict]]:
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: List[List[dict]] = []
    for word in sorted_words:
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > y_tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)
    return lines


def line_text(line: List[dict]) -> str:
    return " ".join(word["text"].strip() for word in sorted(line, key=lambda w: w["x0"]) if word["text"].strip())


def parse_company_name_from_position(words: List[dict], page_width: float, page_height: float) -> str:
    for line in group_words_by_line(words):
        if not line:
            continue
        top = min(word["top"] for word in line)
        x0 = min(word["x0"] for word in line)
        x1 = max(word["x1"] for word in line)
        if not (page_height * 0.09 < top < page_height * 0.18):
            continue
        if x0 > page_width * 0.16 or x1 > page_width * 0.48:
            continue
        return line_text(line)
    return ""


def parse_job_description_from_position(words: List[dict], page_width: float, page_height: float) -> str:
    center_x = page_width / 2
    for line in group_words_by_line(words):
        if not line:
            continue
        top = min(word["top"] for word in line)
        if not (page_height * 0.12 < top < page_height * 0.28):
            continue
        line_center = (min(word["x0"] for word in line) + max(word["x1"] for word in line)) / 2
        if abs(line_center - center_x) > page_width * 0.12:
            continue
        return line_text(line)
    return ""


def parse_job_name_from_position(words: List[dict], page_width: float, page_height: float) -> str:
    center_x = page_width / 2
    candidates = []
    for word in words:
        text = word["text"].strip()
        if not re.fullmatch(r"[A-Z]{1,6}\d{3,}[A-Z0-9]*", text):
            continue
        word_center = (word["x0"] + word["x1"]) / 2
        if abs(word_center - center_x) > page_width * 0.18:
            continue
        if not (page_height * 0.12 < word["top"] < page_height * 0.32):
            continue
        center_score = abs(word_center - center_x)
        top_score = abs(word["top"] - page_height * 0.2)
        candidates.append((center_score + top_score, text))
    return min(candidates)[1] if candidates else ""


def parse_number_of_units(text: str) -> str:
    m = re.search(r"Number\s+of\s+units:\s*(\d+)", text, re.IGNORECASE)
    return m.group(1) if m else ""


def detect_document_type(pdf_path: Path) -> str:
    with pdfplumber.open(str(pdf_path)) as pdf:
        if not pdf.pages:
            raise ValueError("The uploaded PDF has no pages.")
        first_page_text = pdf.pages[0].extract_text() or ""

    if re.search(r"Assembly\s+(?:Medium\s+)?Drawing", first_page_text, re.IGNORECASE):
        return "assembly"
    if re.search(r"(?:^|\n)\s*Schedule(?:\s|$)", first_page_text, re.IGNORECASE):
        return "schedule"
    raise ValueError("Unsupported PDF. Upload an X1 Schedule or Assembly (Detail) PDF.")


def parse_assembly_company_name(words: List[dict], page_width: float, page_height: float) -> str:
    candidates = []
    left_words = [word for word in words if word["x1"] < page_width * 0.48]
    for line in group_words_by_line(left_words):
        if not line:
            continue
        top = min(word["top"] for word in line)
        x0 = min(word["x0"] for word in line)
        if top > page_height * 0.10 or x0 > page_width * 0.12:
            continue
        text = line_text(line)
        if text:
            candidates.append((top, text))
    return min(candidates)[1] if candidates else ""


def parse_assembly_job_description(words: List[dict], page_width: float, page_height: float) -> str:
    center_x = page_width / 2
    candidates = []
    for line in group_words_by_line(words):
        if not line:
            continue
        top = min(word["top"] for word in line)
        if top > page_height * 0.14:
            continue
        x0 = min(word["x0"] for word in line)
        x1 = max(word["x1"] for word in line)
        line_center = (x0 + x1) / 2
        text = line_text(line)
        if abs(line_center - center_x) > page_width * 0.12:
            continue
        if not re.fullmatch(r"[A-Z][A-Z0-9 &'-]*", text):
            continue
        candidates.append((abs(line_center - center_x) + top, text))
    return min(candidates)[1] if candidates else ""


def parse_items(pdf_path: Path, document_type: str | None = None) -> List[Item]:
    document_type = document_type or detect_document_type(pdf_path)
    items: List[Item] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            words = page.extract_words(x_tolerance=1, y_tolerance=1)
            headers = [w for w in words if re.fullmatch(r"#\d+", w['text'])]
            headers = sorted(headers, key=lambda w: w['top'])
            for i, w in enumerate(headers):
                start = w['top']
                end = headers[i + 1]['top'] - 1 if i + 1 < len(headers) else page.height - 8
                # segment text by location: simple textual split from extracted text
                # use regex against page text for each item number
                item_no = int(w['text'][1:])
                # textual segment from #n to next #m or end of page text
                pat = re.compile(rf"#\s*{item_no}\s+([^\n]+)(.*?)(?=(?:#\s*\d+\b)|$)", re.S)
                m = pat.search(text)
                if not m:
                    continue
                desc = clean_desc(m.group(1))
                seg = m.group(2)
                colour = ""
                m_colour = re.search(r"(?:^|\n)\s*Colou?r\s*:\s*([^\n]+)", seg, re.IGNORECASE)
                if m_colour:
                    colour = clean_desc(m_colour.group(1))
                frame = ""
                m_frame = re.search(r"\n([^\n]*\([^\n]*\)[^\n]*)\n", seg)
                if m_frame:
                    frame = m_frame.group(1).strip()
                if not frame:
                    # Sundry-only rows can still be numbered in X1, but they
                    # are not physical units and should not become labels.
                    continue
                suite = ""
                m_suite = re.search(r"\(([^)]+)\)", frame)
                if m_suite:
                    suite = m_suite.group(1).strip()
                elif frame:
                    suite = frame.split()[0]
                flashing = ""
                m_flash = re.search(r"\n(No Head Flashing|[^\n]*Flashing[^\n]*)\n", seg)
                if m_flash:
                    flashing = m_flash.group(1).strip()
                if flashing.lower().startswith('no'):
                    flashing = 'NO Flashing'
                m_wanz = re.search(r"\n(\d+\s*-\s*)?([^\n]*Sill Support[^\n]*)\n", seg)
                wanz = m_wanz.group(2).strip() if m_wanz else ""
                m_kg = re.search(r"Est\. weight:\s*([\d.]+)", seg)
                kg = m_kg.group(1) if m_kg else ""
                if not kg:
                    continue
                items.append(Item(
                    no=item_no,
                    desc=desc,
                    colour=colour,
                    frame=frame,
                    suite=suite,
                    flashing=flashing,
                    wanz=wanz,
                    kg=kg,
                    page_index=page_index,
                    header_top=w['top'],
                    header_bottom=w['bottom'],
                    section_bottom=end,
                ))
    return items


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

    # Schedule reports place their diagram in a 250 x 203 image. Assembly
    # reports contain the same drawing in a larger 720 x 660 image. Normalize
    # the Assembly image to the Schedule canvas before the existing label
    # layout code sees it.
    target_width, target_height = 237, 203
    scale = min(target_width / content.width, target_height / content.height)
    normalized_size = (
        max(1, round(content.width * scale)),
        max(1, round(content.height * scale)),
    )
    content = content.resize(normalized_size, Image.Resampling.LANCZOS)
    schedule_canvas = Image.new("RGB", (250, 203), "white")
    schedule_canvas.paste(
        content,
        (
            (schedule_canvas.width - content.width) // 2,
            (schedule_canvas.height - content.height) // 2,
        ),
    )

    # Reproduce the raster dimensions used when the Schedule image is drawn
    # on an X1 page and rendered at the generator's normal DPI.
    rendered = schedule_canvas.resize(
        (round(187.5 * DPI / 72), round(152.25 * DPI / 72)),
        Image.Resampling.BICUBIC,
    )
    padded = Image.new("RGB", (rendered.width + 80, rendered.height + 80), "white")
    padded.paste(rendered, (40, 40))
    return trim_diagram(padded)


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


def fit_image(path: Path, max_w: float, max_h: float) -> Tuple[float, float]:
    im = Image.open(path)
    w, h = im.size
    scale = min(max_w / w, max_h / h)
    return w * scale, h * scale


def wrap_text(text: str, font_name: str, font_size: float, max_width: float, max_lines: int) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for word in words[1:]:
        test = cur + ' ' + word
        if pdfmetrics.stringWidth(test, font_name, font_size) <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = word
            if len(lines) >= max_lines - 1:
                break
    if len(lines) < max_lines:
        lines.append(cur)
    # if still words left, add ellipsis
    used = sum(len(l.split()) for l in lines)
    if used < len(words):
        last = lines[-1]
        while pdfmetrics.stringWidth(last + '...', font_name, font_size) > max_width and len(last) > 3:
            last = last[:-1]
        lines[-1] = last.rstrip() + '...'
    return lines[:max_lines]


def draw_field(c: canvas.Canvas, x: float, y: float, label: str, value: str, width: float, size: float = 5.2):
    c.setFont('Helvetica-Bold', size)
    c.drawString(x, y, label)
    label_w = pdfmetrics.stringWidth(label, 'Helvetica-Bold', size)
    c.setFont('Helvetica', size)
    c.drawString(x + label_w + 1, y, value)


def fit_text_width(text: str, font_name: str, font_size: float, max_width: float) -> str:
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text
    suffix = "..."
    while text and pdfmetrics.stringWidth(text + suffix, font_name, font_size) > max_width:
        text = text[:-1].rstrip()
    return f"{text}{suffix}" if text else suffix


def text_block_bottom_y(item: Item, block_w: float, y_top: float, field_size: float, line_step: float) -> float:
    ty = y_top - 7

    ty -= line_step

    colour_lines = wrap_text(item.colour, 'Helvetica', field_size, block_w - 24, 2)
    if len(colour_lines) > 1:
        ty -= line_step
    ty -= line_step

    desc_lines = wrap_text(item.desc, 'Helvetica', field_size, block_w - 20, 2)
    if len(desc_lines) > 1:
        ty -= line_step
    ty -= line_step

    ty -= line_step

    flash_lines = wrap_text(item.flashing, 'Helvetica', field_size, block_w - 20, 2)
    if len(flash_lines) > 1:
        ty -= line_step
    ty -= line_step

    wanz_lines = wrap_text(item.wanz, 'Helvetica', field_size, block_w - 18, 2)
    if len(wanz_lines) > 1:
        ty -= line_step
    ty -= line_step

    return ty


def calculate_diagram_scale(
    items: List[Item],
    diagrams: Dict[int, Path],
    block_w: float,
    block_h: float,
    top_margin: float,
    header_space: float,
    bottom_margin: float,
    row_gap: float,
    rows: int,
    cols: int,
    ph: float,
    field_size: float,
    line_step: float,
) -> float:
    scales = []
    for idx, item in enumerate(items):
        img_path = diagrams.get(item.no)
        if not img_path or not img_path.exists():
            continue
        pos = idx % (cols * rows)
        row = pos // cols
        y_top = ph - top_margin - header_space - row * (block_h + row_gap)
        ty = text_block_bottom_y(item, block_w, y_top, field_size, line_step)
        block_bottom = y_top - block_h
        zone_bottom = block_bottom + 2
        zone_top = ty - 4
        max_img_h = max(zone_top - zone_bottom, 10)
        max_img_w = block_w - 2
        with Image.open(img_path) as im:
            w, h = im.size
        if w and h:
            scales.append(min(max_img_w / w, max_img_h / h))
    return min(scales) if scales else 1.0


def make_pdf(items: List[Item], diagrams: Dict[int, Path], out_path: Path, meta: HeaderMeta):
    pw, ph = landscape(A4)
    c = canvas.Canvas(str(out_path), pagesize=landscape(A4))

    cols, rows = 7, 2
    left_margin = 8 * mm
    right_margin = 8 * mm
    top_margin = 8 * mm
    bottom_margin = 8 * mm
    header_space = 10 * mm
    col_gap = 2.0 * mm
    row_gap = 10 * mm
    block_w = (pw - left_margin - right_margin - col_gap * (cols - 1)) / cols
    block_h = (ph - top_margin - bottom_margin - header_space - row_gap * (rows - 1)) / rows
    field_size = 6.4
    line_step = 6.8
    base_diagram_down_shift = 3 * mm
    green_gap_reduction = 13 * mm
    yellow_gap_reduction = 14 * mm
    diagram_scale = calculate_diagram_scale(
        items,
        diagrams,
        block_w,
        block_h,
        top_margin,
        header_space,
        bottom_margin,
        row_gap,
        rows,
        cols,
        ph,
        field_size,
        line_step,
    )

    for idx, item in enumerate(items):
        page_idx = idx // (cols * rows)
        pos = idx % (cols * rows)
        row = pos // cols
        col = pos % cols
        x = left_margin + col * (block_w + col_gap)
        y_top = ph - top_margin - header_space - row * (block_h + row_gap)
        text_down_shift = yellow_gap_reduction + (green_gap_reduction if row == 0 else 0)
        row_diagram_down_shift = yellow_gap_reduction if row == 0 else 0
        if pos == 0:
            header_font = 'Helvetica-Bold'
            header_size = 9 * 1.3
            quote_size = header_size * 3
            header_up_shift = 12.5 * mm
            header_y = ph - top_margin - 2 - green_gap_reduction - yellow_gap_reduction + header_up_shift
            c.setFont(header_font, header_size)
            quote_label = 'Qte#: '
            c.drawString(left_margin, header_y, quote_label)
            quote_x = left_margin + pdfmetrics.stringWidth(quote_label, header_font, header_size)
            c.setFont(header_font, quote_size)
            c.drawString(quote_x, header_y, meta.quote_no)
            header_end_x = quote_x + pdfmetrics.stringWidth(meta.quote_no, header_font, quote_size)
            if meta.number_of_units:
                units_text = f'Number of units: {meta.number_of_units}'
                units_x = header_end_x + 4 * mm
                c.setFont(header_font, header_size)
                c.drawString(units_x, header_y, units_text)
                header_end_x = units_x + pdfmetrics.stringWidth(units_text, header_font, header_size)
            company_gap = pdfmetrics.stringWidth('abcde', header_font, header_size)
            company_x = header_end_x + company_gap
            job_description = meta.job_description or meta.title
            right_edge = pw - right_margin
            job_gap = 5 * mm
            available_job_width = right_edge - company_x - job_gap
            job_text = fit_text_width(job_description, header_font, header_size, min(60 * mm, available_job_width)) if job_description else ''
            job_width = pdfmetrics.stringWidth(job_text, header_font, header_size)
            company_width = pdfmetrics.stringWidth(meta.company_name, header_font, header_size) if meta.company_name else 0
            job_x = min(company_x + company_width + job_gap, right_edge - job_width)
            c.setFont(header_font, header_size)
            if meta.company_name:
                c.drawString(
                    company_x,
                    header_y,
                    fit_text_width(meta.company_name, header_font, header_size, job_x - company_x - job_gap),
                )
            if job_text:
                c.drawString(
                    job_x,
                    header_y,
                    job_text,
                )
        # origin top-left concept
        ty = y_top - text_down_shift - 7

        # text block
        draw_field(c, x, ty, 'Item:', str(item.no), block_w, size=field_size)
        ty -= line_step
        colour_lines = wrap_text(item.colour, 'Helvetica', field_size, block_w - 24, 2)
        c.setFont('Helvetica-Bold', field_size)
        c.drawString(x, ty, 'Colour:')
        c.setFont('Helvetica', field_size)
        c.drawString(x + pdfmetrics.stringWidth('Colour:', 'Helvetica-Bold', field_size) + 1, ty, colour_lines[0])
        if len(colour_lines) > 1:
            ty -= line_step
            c.drawString(x + 10, ty, colour_lines[1])
        ty -= line_step
        desc_lines = wrap_text(item.desc, 'Helvetica', field_size, block_w - 20, 2)
        c.setFont('Helvetica-Bold', field_size)
        c.drawString(x, ty, 'Desc:')
        c.setFont('Helvetica', field_size)
        c.drawString(x + pdfmetrics.stringWidth('Desc:', 'Helvetica-Bold', field_size) + 1, ty, desc_lines[0])
        if len(desc_lines) > 1:
            ty -= line_step
            c.drawString(x + 10, ty, desc_lines[1])
        ty -= line_step
        suite_val = item.suite or item.frame[:18]
        draw_field(c, x, ty, 'Suite:', suite_val, block_w, size=field_size)
        ty -= line_step
        flash_lines = wrap_text(item.flashing, 'Helvetica', field_size, block_w - 20, 2)
        c.setFont('Helvetica-Bold', field_size)
        c.drawString(x, ty, 'Flash:')
        c.setFont('Helvetica', field_size)
        c.drawString(x + pdfmetrics.stringWidth('Flash:', 'Helvetica-Bold', field_size) + 1, ty, flash_lines[0])
        if len(flash_lines) > 1:
            ty -= line_step
            c.drawString(x + 10, ty, flash_lines[1])
        ty -= line_step
        wanz_lines = wrap_text(item.wanz, 'Helvetica', field_size, block_w - 18, 2)
        c.setFont('Helvetica-Bold', field_size)
        c.drawString(x, ty, 'WAN:')
        c.setFont('Helvetica', field_size)
        c.drawString(x + pdfmetrics.stringWidth('WAN:', 'Helvetica-Bold', field_size) + 1, ty, wanz_lines[0])
        if len(wanz_lines) > 1:
            ty -= line_step
            c.drawString(x + 10, ty, wanz_lines[1])
        ty -= line_step
        draw_field(c, x, ty, 'Kg:', item.kg, block_w, size=field_size)

        # diagram zone: place directly under the text block to reduce blank space
        img_path = diagrams.get(item.no)
        block_bottom = y_top - block_h
        zone_bottom = block_bottom + 2
        diagram_layout_ty = text_block_bottom_y(item, block_w, y_top, field_size, line_step)
        zone_top = diagram_layout_ty - 4
        max_img_h = max(zone_top - zone_bottom, 10)
        max_img_w = block_w - 2
        if img_path and img_path.exists():
            with Image.open(img_path) as im:
                img_w, img_h = im.size
            local_scale = min(max_img_w / img_w, max_img_h / img_h)
            draw_scale = min(diagram_scale, local_scale)
            draw_w, draw_h = img_w * draw_scale, img_h * draw_scale
            ix = x + (block_w - draw_w) / 2
            centered_iy = zone_bottom + max((max_img_h - draw_h) / 2, 0)
            iy = max(zone_bottom, centered_iy - base_diagram_down_shift) - row_diagram_down_shift
            c.drawImage(ImageReader(str(img_path)), ix, iy, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')

        if pos == cols * rows - 1 and idx != len(items) - 1:
            c.showPage()

    c.save()


def generate_despatch_label(input_path: Path, output_path: Path, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)

    document_type = detect_document_type(input_path)
    items = parse_items(input_path, document_type)
    if not items:
        raise ValueError("No physical units were found in the uploaded PDF.")
    with pdfplumber.open(str(input_path)) as pdf:
        first_page = pdf.pages[0]
        first_text = first_page.extract_text() or ''
        first_words = first_page.extract_words(x_tolerance=1, y_tolerance=1)
        company_name = parse_company_name_from_position(first_words, first_page.width, first_page.height)
        job_description = parse_job_description_from_position(first_words, first_page.width, first_page.height)
        job_name = parse_job_name_from_position(first_words, first_page.width, first_page.height)
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    meta = parse_header_meta(first_text)
    if document_type == "assembly":
        meta.company_name = parse_assembly_company_name(first_words, first_page.width, first_page.height)
        meta.job_description = parse_assembly_job_description(first_words, first_page.width, first_page.height)
        meta.number_of_units = str(len(items))
    else:
        if company_name:
            meta.company_name = company_name
        if job_name:
            meta.title = job_name
        if job_description:
            meta.job_description = job_description
        elif meta.title:
            meta.job_description = meta.title
        meta.number_of_units = parse_number_of_units(full_text)
    diagrams = extract_diagram_images(input_path, items, workdir / 'diagrams', document_type)
    make_pdf(items, diagrams, output_path, meta)
    return output_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--workdir', default='/mnt/data/x1_label_work')
    args = ap.parse_args()

    pdf_path = Path(args.input)
    out_path = Path(args.output)
    workdir = Path(args.workdir)
    generate_despatch_label(pdf_path, out_path, workdir)
    print(f'Wrote {out_path}')

if __name__ == '__main__':
    main()
