"""Regression: item references in descriptions/notes are not item headings."""
import os
from pathlib import Path
import pytest
from reportlab.pdfgen import canvas
from x1_despatch_label_real_diagram import parse_items, item_heading_words

def test_references_and_notes_preserve_two_sections(tmp_path):
    pdf = tmp_path / 'references.pdf'
    c = canvas.Canvas(str(pdf), pagesize=(595,842))
    c.drawString(30,800,'Schedule')
    for number, description, top, weight in [
        (14,'FAMILY BELOW #15',700,'36.72'), (15,'FAMILY TOP OF #14',440,'28.37')
    ]:
        c.setFont('Helvetica-Bold',10)
        c.drawString(230,top,f'#{number}  {description}')
        c.setFont('Helvetica',10)
        c.drawString(250,top-14,'Quantity: 1')
        c.drawString(250,top-30,'Frame: A/W Frame (TL40) Awning Window')
        c.drawString(250,top-46,'Colour: AEONOX Black')
        c.drawString(250,top-62,f'Est. weight: {weight} kg/ea')
        c.drawString(30,top-170,'Sundry')
        c.drawString(30,top-184,'MULLION SAME POSITION OF #15')
    c.save()
    items=parse_items(pdf)
    assert [(i.no,i.desc,i.kg) for i in items]==[
        (14,'FAMILY BELOW #15','36.72'),(15,'FAMILY TOP OF #14','28.37')]
    assert all(i.section_bottom > i.header_bottom for i in items)
    assert len({i.no for i in items})==len(items)

def test_inline_hardware_number_is_not_a_header():
    def word(text,x,y): return dict(text=text,x0=x,x1=x+15,top=y,bottom=y+8)
    words=[word('#2',217,100),word('Door',245,100),word('Quantity:',240,114),
           word('Screw',30,250),word('#2',140,250),word('DRV',160,250)]
    assert [w['text'] for w in item_heading_words(words,595)]==['#2']

def test_actual_50241():
    value=os.environ.get('X1_HEADING_SAMPLE')
    if not value: pytest.skip('Set X1_HEADING_SAMPLE to 50241 Schedule.pdf')
    items=parse_items(Path(value))
    assert [(i.no,i.desc,i.kg) for i in items]==[
        (14,'FAMILY BELOW #15','36.72'),(15,'FAMILY TOP OF #14','28.37')]
