"""Read complete label fields directly from the uploaded PDF."""
import re
from pathlib import Path
import pdfplumber
from .extract import Item, detect_document_type, item_heading_words


def read_field(text, name, keep_name=False):
    # Stop at the next named field, preserving wrapped values and product codes.
    match = re.search(rf'(?mi)^\s*({name})\s*:\s*(.*)', text)
    if not match:
        return ''
    parts = [match[2].strip()]
    for line in text[match.end():].splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r'[A-Za-z][A-Za-z .()/&-]*:', line) or re.match(r'(?:Sundry|Profile|Trim Size|#\d+)', line):
            break
        parts.append(line)
    value = ' '.join(' '.join(parts).split())
    return f'{match[1]}: {value}' if keep_name else value


def read_labels(path: Path):
    kind = detect_document_type(path)
    items = []
    with pdfplumber.open(path) as pdf:
        quote_match = re.search(r'Quote\s+No\.?\s*(\d+)', pdf.pages[0].extract_text() or '', re.I)
        quote = quote_match[1] if quote_match else ''
        if not quote:
            raise ValueError('Could not read the Quote No. from this PDF.')
        for page_index, page in enumerate(pdf.pages):
            words = page.extract_words(x_tolerance=1, y_tolerance=1)
            headings = item_heading_words(words, page.width)
            for idx, heading in enumerate(headings):
                end = headings[idx+1]['top']-1 if idx+1<len(headings) else page.height-8
                # Only the specification column: drawing dimensions never enter fields.
                text = page.crop((heading['x0']-1, heading['bottom'], page.width, end)).extract_text() or ''
                frame = read_field(text, 'Frame')
                if not frame:
                    continue  # Numbered sundry rows are not physical items.
                quantity_top = min(w['top'] for w in words if w['text']=='Quantity:'
                                   and w['top']>heading['top'] and w['x0']>=heading['x0'])
                description = page.crop((heading['x0'], heading['top'], page.width, quantity_top-1)).extract_text() or ''
                description = re.sub(r'^#\s*\d+\s*', '', description)
                description = ' '.join(description.split())
                suite = re.search(r'\(([^)]+)\)', frame)
                items.append(Item(no=int(heading['text'][1:]), desc=description,
                    colour=read_field(text, 'Colou?r'), frame=frame,
                    suite=suite[1].strip() if suite else frame,
                    flashing=read_field(text, 'Head Flashing', True),
                    wanz=read_field(text, 'Cill Support', True), kg='',
                    page_index=page_index, header_top=heading['top'],
                    header_bottom=heading['bottom'], section_bottom=end))
    if not items:
        raise ValueError('No physical items were found for labels.')
    if len({i.no for i in items}) != len(items):
        raise ValueError('Repeated item numbers were found. Upload one Schedule or Assembly PDF for one quote.')
    return quote, kind, items
