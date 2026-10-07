"""Fixed Avery L7173 positions measured from the user's Word template."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

LABEL_WIDTH = 280.8  # 5616 twips = 99.06 mm
LABEL_HEIGHT = 161.55  # 3231 twips = 56.99125 mm
X_POSITIONS = (13.25, 301.25)
Y_POSITIONS = (17.10, 178.70, 340.25, 501.85, 663.40)
BLUE = colors.HexColor('#2e3477')
REFERENCE = Path(__file__).parent / 'assets' / 'reference.png'


def label_box(index):
    position = index % 10
    return X_POSITIONS[position % 2], Y_POSITIONS[position // 2], LABEL_WIDTH, LABEL_HEIGHT


def wrap_complete(value, size, width):
    """Wrap every character, including single overlong product codes."""
    lines, current = [], ''
    for word in value.split():
        candidate = f'{current} {word}'.strip()
        if stringWidth(candidate, 'Helvetica', size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ''
        for character in word:
            if current and stringWidth(current+character, 'Helvetica', size)>width:
                lines.append(current)
                current = ''
            current += character
    if current:
        lines.append(current)
    return lines or ['']


def fit_field(label, value, width, height, maximum=13.4):
    value = str(value or '-')
    # Shrink the value and its prefix together, without truncation or ellipses.
    size = maximum
    while True:
        prefix = stringWidth(label, 'Helvetica-Bold', size) + size*.16
        lines = wrap_complete(value, size, max(width-prefix, .1))
        if len(lines)*size*1.06 <= height and prefix < width:
            return size, prefix, lines
        size *= .95
        if size < .3:
            raise ValueError(f'The {label} value is too long to fit on a label.')


def draw_field(c, label, value, x, top, width, height):
    size, prefix, lines = fit_field(label, value, width, height)
    baseline = top-size*.82
    c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold', size)
    c.drawString(x, baseline, label)
    c.setFont('Helvetica', size)
    for line in lines:
        c.drawString(x+prefix, baseline, line)
        baseline -= size*1.06


def draw_label(c, item, quote, diagram, index):
    x, top, width, height = label_box(index)
    y = A4[1]-top-height
    c.saveState()
    c.translate(x, y)
    # Each label owns a fixed clipping area. No element can touch another label.
    clip = c.beginPath(); clip.rect(0, 0, width, height)
    c.clipPath(clip, stroke=0)
    header_height = 35.7
    c.setFillColor(BLUE)
    c.rect(0, height-header_height, width, header_height, fill=1, stroke=0)
    # Render only the original logo portion through a PDF clip; no generated logo.
    c.saveState()
    logo_clip = c.beginPath(); logo_clip.rect(0, height-header_height, 94, header_height)
    c.clipPath(logo_clip, stroke=0)
    c.drawImage(str(REFERENCE), 0, height-height, width=width, height=height)
    c.restoreState()
    title = f'Quote {quote}'
    title_size = min(24, 164/stringWidth(title, 'Helvetica-Bold', 1))
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold', title_size)
    c.drawRightString(width-6, height-header_height/2-title_size*.34, title)
    # Positions follow the supplied reference: six fields on the left, drawing right.
    fields = [('Item:', str(item.no), 42, 14), ('Desc:', item.desc, 57, 14),
              ('Colour:', item.colour, 72, 14), ('Suite:', item.suite, 87, 14),
              ('Flash:', item.flashing, 102, 29), ('WAN:', item.wanz, 131, 28)]
    for label, value, offset, field_height in fields:
        draw_field(c, label, value, 6.8, height-offset, 179, field_height)
    reader = ImageReader(str(diagram))
    iw, ih = reader.getSize()
    available_w, available_h = 85, 102
    scale = min(available_w/iw, available_h/ih)
    dw, dh = iw*scale, ih*scale
    c.drawImage(reader, 191+(available_w-dw)/2, 18+(available_h-dh)/2,
                width=dw, height=dh, preserveAspectRatio=True, mask='auto')
    c.restoreState()


def make_labels(items, diagrams, output, quote):
    c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
    c.setTitle(f'Quote {quote} - Avery L7173 Item Labels')
    c.setAuthor('LIDAR Windows & Doors')
    c.setViewerPreference('PrintScaling', 'None')
    for index, item in enumerate(items):
        if index and index % 10 == 0:
            c.showPage()
        draw_label(c, item, quote, diagrams[item.no], index)
    c.save()
