#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

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
    printed: str
    address: str


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
    title = ""
    lines = [ln.strip() for ln in first_page_text.splitlines() if ln.strip()]
    template_idx = next((i for i, ln in enumerate(lines) if 'TEMPLATE' in ln.upper()), None)
    schedule_idx = next((i for i, ln in enumerate(lines) if ln.startswith('Schedule')), None)
    if template_idx is not None and schedule_idx is not None:
        candidates = []
        for ln in lines[template_idx + 1:schedule_idx]:
            if ':' in ln:
                continue
            if any(ch.isdigit() for ch in ln):
                continue
            if ln.upper() == 'ROLLeston'.upper():
                continue
            candidates.append(ln)
        if candidates:
            # prefer first non-duplicate pair like Harrow Green
            title = candidates[0]
    address = ""
    for ln in lines:
        if looks_like_address(ln):
            address = ln
            break
    return HeaderMeta(
        quote_no=quote_no,
        title=title,
        printed=printed,
        address=address,
    )


def parse_items(pdf_path: Path) -> List[Item]:
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
                frame = ""
                m_frame = re.search(r"\n([^\n]*\([^\n]*\)[^\n]*)\n", seg)
                if m_frame:
                    frame = m_frame.group(1).strip()
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
                items.append(Item(
                    no=item_no,
                    desc=desc,
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
    items.sort(key=lambda x: x.no)
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

    # Keep the full diagram including the lower dimension line, but stop before
    # the next large blank gap that precedes Sundry / next item content.
    bottom = int(nz[-1])
    gaps = np.diff(nz)
    large_gap_positions = np.where(gaps >= 14)[0]
    if len(large_gap_positions):
        # Prefer the last large gap that occurs after the diagram area starts.
        chosen = None
        for idx in large_gap_positions:
            if nz[idx] > h * 0.35:
                chosen = idx
        if chosen is not None:
            bottom = int(nz[chosen])
    bottom = min(bottom + 10, h - 1)

    crop2 = crop.crop((0, top, w, bottom))
    mask2 = dark_mask(crop2)
    coords = np.argwhere(mask2)
    if len(coords) == 0:
        return crop2
    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0)
    x0 = max(int(x0) - 8, 0)
    x1 = min(int(x1) + 8, crop2.width - 1)
    y0 = max(int(y0) - 6, 0)
    y1 = min(int(y1) + 10, crop2.height - 1)
    return crop2.crop((x0, y0, x1, y1))


def extract_diagram_images(pdf_path: Path, items: List[Item], out_dir: Path) -> Dict[int, Path]:
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
            fpage = doc.load_page(pidx)
            pix = fpage.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            for item in page_items[pidx]:
                objs = []
                for obj in list(page.lines) + list(page.rects):
                    x0, x1 = obj['x0'], obj['x1']
                    top, bottom = obj['top'], obj['bottom']
                    if x1 < 230 and top > item.header_top + 8 and bottom < item.section_bottom - 5:
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
                    y1 = min(page.height, y1 + 8)
                    crop = img.crop((int(x0 * scale), int(y0 * scale), int(x1 * scale), int(y1 * scale)))
                else:
                    x0_pt = 18
                    x1_pt = 225
                    y0_pt = item.header_top + 4
                    y1_pt = item.section_bottom - 4
                    crop = img.crop((int(x0_pt * scale), int(y0_pt * scale), int(x1_pt * scale), int(y1_pt * scale)))
                    crop = trim_diagram(crop)
                out_path = out_dir / f"diagram_{item.no}.png"
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


def make_pdf(items: List[Item], diagrams: Dict[int, Path], out_path: Path, meta: HeaderMeta):
    pw, ph = landscape(A4)
    c = canvas.Canvas(str(out_path), pagesize=landscape(A4))

    cols, rows = 8, 2
    left_margin = 6 * mm
    right_margin = 6 * mm
    top_margin = 7 * mm
    bottom_margin = 7 * mm
    header_space = 10 * mm
    col_gap = 2.0 * mm
    row_gap = 10 * mm
    block_w = (pw - left_margin - right_margin - col_gap * (cols - 1)) / cols
    block_h = (ph - top_margin - bottom_margin - header_space - row_gap * (rows - 1)) / rows

    for idx, item in enumerate(items):
        page_idx = idx // (cols * rows)
        pos = idx % (cols * rows)
        row = pos // cols
        col = pos % cols
        x = left_margin + col * (block_w + col_gap)
        y_top = ph - top_margin - header_space - row * (block_h + row_gap)
        if pos == 0:
            c.setFont('Helvetica-Bold', 9)
            c.drawString(left_margin, ph - top_margin - 2, f'Qte#: {meta.quote_no}')
            if idx == 0 and meta.address:
                c.setFont('Helvetica-Bold', 10)
                c.drawCentredString(pw / 2, ph - top_margin - 2, meta.address)
        # origin top-left concept
        ty = y_top - 7

        # text block
        field_size = 5.0
        line_step = 5.35
        # first line qte
        draw_field(c, x, ty, 'Qte#:', meta.quote_no, block_w, size=field_size)
        ty -= line_step
        title_lines = wrap_text(meta.title, 'Helvetica', field_size, block_w - 18, 2)
        c.setFont('Helvetica-Bold', field_size)
        c.drawString(x, ty, 'Title:')
        c.setFont('Helvetica', field_size)
        c.drawString(x + pdfmetrics.stringWidth('Title:', 'Helvetica-Bold', field_size) + 1, ty, title_lines[0])
        if len(title_lines) > 1:
            ty -= line_step
            c.drawString(x + 10, ty, title_lines[1])
        ty -= line_step
        draw_field(c, x, ty, 'Item:', str(item.no), block_w, size=field_size)
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
        printed_y = block_bottom + 6
        zone_bottom = printed_y + 7
        zone_top = ty - 4
        max_img_h = max(zone_top - zone_bottom, 10)
        max_img_w = block_w - 2
        if img_path and img_path.exists():
            draw_w, draw_h = fit_image(img_path, max_img_w, max_img_h)
            ix = x + (block_w - draw_w) / 2
            iy = zone_bottom + max((max_img_h - draw_h) / 2, 0)
            c.drawImage(ImageReader(str(img_path)), ix, iy, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
        # printed line
        c.setFont('Helvetica', 4.7)
        c.drawString(x + 1, printed_y, f'Printed on:{meta.printed}')

        if pos == cols * rows - 1 and idx != len(items) - 1:
            c.showPage()

    c.save()


def generate_despatch_label(input_path: Path, output_path: Path, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)

    items = parse_items(input_path)
    with pdfplumber.open(str(input_path)) as pdf:
        first_text = pdf.pages[0].extract_text() or ''
    meta = parse_header_meta(first_text)
    diagrams = extract_diagram_images(input_path, items, workdir / 'diagrams')
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
