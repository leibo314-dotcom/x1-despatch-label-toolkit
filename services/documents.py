"""Read-only source facts. No delivery, colour, or width decisions here."""
from dataclasses import dataclass, replace
from pathlib import Path
import re
import pymupdf


@dataclass(frozen=True)
class Profile:
    code: str
    length: float | None
    quantity: float | None
    page: int


@dataclass(frozen=True)
class Item:
    number: int
    description: str
    frame: str
    colour: str
    quantity: int | None
    pages: tuple[int, ...]
    profiles: tuple[Profile, ...]
    text: str


@dataclass(frozen=True)
class Document:
    path: Path
    name: str
    quote: str
    kind: str
    items: tuple[Item, ...]


def field(text, name):
    match = re.search(rf"(?mi)^\s*{name}\s*:\s*([^\n]+)", text)
    return re.sub(r"\s+", " ", match[1]).strip() if match else ""


def profile_rows(spans, page):
    rows = []
    for span in spans:
        match = re.match(r"^(V\d{3}[A-Z]?|X\d{3})\s*-", span['text'])
        if not match:
            continue
        x, y = span['bbox'][:2]
        # Read actual columns, not numbers in descriptions (58mm, TL40, etc.).
        headers = [s for s in spans if s['text'].strip() == 'Profile'
                   and abs(s['bbox'][0]-x)<6 and s['bbox'][1]<y]
        header = max(headers, key=lambda s:s['bbox'][1]) if headers else None
        columns = {} if header is None else {
            s['text'].strip(): s['bbox'][0] for s in spans
            if abs(s['bbox'][1]-header['bbox'][1])<3
            and x < s['bbox'][0] < x+280
            and s['text'].strip() in ('Length','Qty','Comment')}
        values = []
        for column, next_column in [('Length','Qty'),('Qty','Comment')]:
            lo, hi = columns.get(column), columns.get(next_column)
            candidates = [] if lo is None or hi is None else [s['text'].strip() for s in spans
                if abs(s['bbox'][1]-y)<2 and lo-3<=s['bbox'][0]<hi-3
                and re.fullmatch(r'\d+(?:\.\d+)?',s['text'].strip())]
            values.append(float(candidates[0]) if len(candidates)==1 else None)
        rows.append(Profile(match[1],*values,page))
    return tuple(rows)


def read_document(path: Path, name: str) -> Document:
    items = []
    with pymupdf.open(path) as pdf:
        if not len(pdf) or pdf.needs_pass:
            raise ValueError('Empty or password-protected PDF.')
        first = pdf[0].get_text(sort=True)
        quote_match = re.search(r'Quote\s+No\.?\s*(\d+)', first, re.I)
        quote = quote_match[1] if quote_match else ''
        kind = ('assembly' if re.search(r'Assembly\s+(?:Medium\s+)?Drawing',first,re.I)
                else 'schedule' if re.search(r'(?mi)^\s*Schedule\b',first)
                else 'bom' if re.search(r'Stock Requirements|Bill of Materials|\bBOM\b',first,re.I)
                else 'unknown')
        for page_number, page in enumerate(pdf,1):
            spans = [s for b in page.get_text('dict')['blocks'] if 'lines' in b
                     for line in b['lines'] for s in line['spans']]
            headings = sorted([s for s in spans if re.match(r'^#\s*\d+\b(?!\.)',s['text'].strip())],
                              key=lambda s:s['bbox'][1])
            if not headings:
                if items and kind in ('assembly','bom'):
                    last = items[-1]
                    items[-1]=replace(last,pages=last.pages+(page_number,),
                        profiles=last.profiles+profile_rows(spans,page_number),
                        text=last.text+'\n'+page.get_text(sort=True))
                continue
            for n, heading in enumerate(headings):
                top = heading['bbox'][1]-1
                bottom = headings[n+1]['bbox'][1]-1 if n+1<len(headings) else page.rect.height-25
                text = page.get_text(clip=pymupdf.Rect(0,top,page.rect.width,bottom),sort=True)
                number = int(re.match(r'^#\s*(\d+)',heading['text'].strip())[1])
                desc = re.search(rf'#\s*{number}\b\s*([^\n]*)',text)
                frame = field(text,'Frame')
                if not frame and kind=='schedule':
                    candidates=[line.strip() for line in text.splitlines() if re.search(r'\([^)]*\)',line)]
                    frame=candidates[0] if candidates else ''
                quantity=field(text,'Quantity')
                items.append(Item(number,desc[1].strip() if desc else '',frame,
                    field(text,'Colou?r'),int(quantity) if quantity.isdigit() else None,
                    (page_number,),profile_rows([s for s in spans if top<=s['bbox'][1]<bottom],page_number),text))
    return Document(path,name,quote,kind,tuple(items))


def read_sources(inputs):
    return tuple(read_document(Path(source['path']),source['name']) for source in inputs)


def require_one_quote(documents):
    if len(documents)>1 and (any(not d.quote for d in documents) or len({d.quote for d in documents})!=1):
        raise ValueError('Upload documents for one quote with a readable Quote No.; different or unidentified quotes cannot be combined.')
