"""Printing geometry, full text preservation and independent output failures."""
import io
from pathlib import Path
from dataclasses import replace
import pymupdf
import pytest
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth, getAscentDescent
from features.item_labels.render import (
    label_box, fit_field, make_labels, wrap_complete, PRINT_INSET, BODY_X, BODY_WIDTH,
    ITEM_SIZE, DESC_SIZE, DESC_TOP, DESC_HEIGHT, DESC_MAX_LINES,
)
from features.item_labels.source import read_labels
from features.item_labels.service import generate_item_labels


def source(path, count=2, assembly=False, title=None):
    c = canvas.Canvas(str(path), pagesize=A4)
    for number in range(1, count+1):
        c.setFont('Helvetica', 10)
        c.drawString(25, 815, title or ('Assembly Drawing' if assembly else 'Schedule'))
        c.drawString(410, 815, 'Quote No. 50364')
        c.setFont('Helvetica-Bold', 10)
        c.drawString(230, 740, f'#{number} MASTER BED D{number:02d}')
        c.setFont('Helvetica', 10)
        fields=['Quantity: 3', 'Frame: Slider (TL40) Sliding Door',
                'Colour: AEONOX Black', 'Head Flashing: No Head Flashing',
                'Cill Support: 00470 - 20mm Sill Support', 'Glass: Clear']
        for n, field in enumerate(fields): c.drawString(230, 724-15*n, field)
        if assembly:
            diagram=Image.new('RGB',(720,660),'white'); draw=ImageDraw.Draw(diagram)
            draw.rectangle((130,50,530,590),outline='black',width=5)
            c.drawImage(ImageReader(diagram),20,400,200,190)
        else:
            c.rect(70,565,95,130)
            c.drawString(90,705,'1967'); c.drawString(25,635,'2180')
        c.showPage()
    c.save()
    return path


@pytest.mark.parametrize('assembly', [False,True])
def test_source_fields_and_one_label_per_item_not_quantity(tmp_path, assembly):
    src=source(tmp_path/'source.pdf', assembly=assembly)
    quote, kind, items=read_labels(src)
    assert quote=='50364' and len(items)==2
    assert items[0].desc=='MASTER BED D01'
    assert items[0].flashing=='Head Flashing: No Head Flashing'
    assert items[0].wanz=='Cill Support: 00470 - 20mm Sill Support'
    assert items[0].colour=='AEONOX Black'
    info=generate_item_labels(src,tmp_path/'labels.pdf',tmp_path/'work')
    assert info==dict(quote='50364',items=2,pages=1)
    with pymupdf.open(tmp_path/'labels.pdf') as pdf:
        text=pdf[0].get_text()
        assert text.count('Item:')==2
        assert all(field not in text for field in ('Desc:', 'Colour:', 'Suite:', 'Flash:', 'WAN:'))
        assert len(pdf[0].get_image_info())==4  # Original logo and item drawing, per label.


@pytest.mark.parametrize('title', [
    'Assembly Drawing (Short)', 'Assembly Short Drawing',
    'Short Assembly Drawing', 'Assembly Medium Drawing (Details)',
])
def test_assembly_variants_generate_labels_through_upload(tmp_path, monkeypatch, title):
    import app
    monkeypatch.delenv('BLOB_READ_WRITE_TOKEN',raising=False)
    monkeypatch.setattr(app,'JOBS_DIR',tmp_path/'jobs')
    src=source(tmp_path/'short.pdf',assembly=True,title=title)
    client=app.app.test_client()
    response=client.post('/generate',data={'independent_outputs':'1',
        'pdf_file':(io.BytesIO(src.read_bytes()),'short-assembly.pdf')})
    job=response.location.split('/result/')[1].split('?')[0]
    result=client.post(f'/api/jobs/{job}/outputs/labels',json={})
    assert result.status_code==200 and result.json['items']==2
    download=client.get('/download-labels/'+job)
    with pymupdf.open(stream=download.data,filetype='pdf') as pdf:
        assert pdf[0].get_text().count('Quote 50364')==2


def test_eleven_items_template_positions_and_blank_unused_slots(tmp_path):
    src=source(tmp_path/'source.pdf', count=11)
    generate_item_labels(src,tmp_path/'labels.pdf',tmp_path/'work')
    with pymupdf.open(tmp_path/'labels.pdf') as pdf:
        assert len(pdf)==2
        for p, expected in zip(pdf,[10,1]):
            assert tuple(p.rect)[2:]==pytest.approx(A4, abs=.001)
            assert p.get_text().count('Quote 50364')==expected
            headers=[d['rect'] for d in p.get_drawings() if d['fill'] and d['rect'].width>250]
            assert len(headers)==expected
            for idx,rect in enumerate(headers):
                x,y,w,h=label_box(idx)
                scale=min((w-2*PRINT_INSET)/w,(h-2*PRINT_INSET)/h)
                assert (rect.x0,rect.y0,rect.width)==pytest.approx(
                    (x+(w-w*scale)/2,y+(h-h*scale)/2,w*scale),abs=.001)
            # Measure all rendered ink against the actual rounded Word edges.
            # This catches background/image leakage, not only text overflow.
            import numpy as np
            raster_scale=3
            pix=p.get_pixmap(matrix=pymupdf.Matrix(raster_scale,raster_scale),alpha=False)
            pixels=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
            yy,xx=np.where(pixels.min(axis=2)<245)
            px,py=(xx+.5)/raster_scale,(yy+.5)/raster_scale
            safe=np.zeros(len(px),dtype=bool)
            for idx in range(expected):
                x,y,w,h=label_box(idx)
                # Rounded-outline signed distance: Word corner radius = 8.5 pt.
                qx=np.abs(px-(x+w/2))-(w/2-8.5)
                qy=np.abs(py-(y+h/2))-(h/2-8.5)
                distance=np.hypot(np.maximum(qx,0),np.maximum(qy,0))+np.minimum(np.maximum(qx,qy),0)-8.5
                safe |= distance <= -2*72/25.4 + 1/raster_scale
            assert safe.all(), 'Printed pixels escaped the 2 mm safety inset'
        preferences=int(pdf.xref_get_key(pdf.pdf_catalog(),'ViewerPreferences')[1].split()[0])
        assert pdf.xref_get_key(preferences,'PrintScaling')==('name','/None')


def test_long_values_shrink_and_keep_every_character(tmp_path):
    values=['Master bedroom extra long description at rear of building near the stairwell',
            'A'*90, 'Unit 15 level 1 living room west elevation full height sliding door '*4]
    for value in values:
        size,prefix,lines=fit_field('',value,BODY_WIDTH,DESC_HEIGHT,
                                  maximum=DESC_SIZE,font_name='Helvetica-Bold',max_lines=DESC_MAX_LINES)
        assert size<DESC_SIZE
        assert prefix==0 and len(lines)<=3
        assert ''.join(''.join(lines).split())==''.join(value.split())
        assert len(lines)*size*1.06<=DESC_HEIGHT
        assert all(stringWidth(line,'Helvetica-Bold',size)<=BODY_WIDTH for line in lines)
    src=source(tmp_path/'source.pdf', count=1)
    quote,_,items=read_labels(src)
    long_items=[replace(items[0],no=n+1,desc=value) for n,value in enumerate(values)]
    diagram=tmp_path/'diagram.png'; Image.new('RGB',(50,50),'white').save(diagram)
    make_labels(long_items,{item.no:diagram for item in long_items},tmp_path/'long.pdf',quote)
    with pymupdf.open(tmp_path/'long.pdf') as pdf:
        text=''.join(pdf[0].get_text().split())
        for value in values: assert ''.join(value.split()) in text
        assert '...' not in text
        assert 'Desc:' not in text
        spans=[s for b in pdf[0].get_text('dict')['blocks'] if 'lines' in b
               for line in b['lines'] for s in line['spans']]
        assert any('Master bedroom' in s['text'] and s['font']=='Helvetica-Bold' for s in spans)
        assert any(s['text'].strip() in ('1','Item: 1','Item:1') and s['font']=='Helvetica-Bold' for s in spans)
        # The rendered description rows use the whole left column, without an
        # invisible prefix indent, and stay above the bottom and left of drawing.
        for idx,item in enumerate(long_items):
            x,y,w,h=label_box(idx)
            scale=min((w-2*PRINT_INSET)/w,(h-2*PRINT_INSET)/h)
            left=x+(w-w*scale)/2+BODY_X*scale
            top=y+(h-h*scale)/2+DESC_TOP*scale
            area=pymupdf.Rect(left-1,top-10,left+BODY_WIDTH*scale+1,top+DESC_HEIGHT*scale+1)
            rows=[line for b in pdf[0].get_text('dict',clip=area)['blocks'] if 'lines' in b
                  for line in b['lines'] if line['spans'][0]['origin'][1]>=top]
            assert 1<=len(rows)<=3
            assert ''.join(''.join(s['text'] for row in rows for s in row['spans']).split())==''.join(item.desc.split())
            for row in rows:
                assert row['bbox'][0]==pytest.approx(left,abs=.01)
                assert row['bbox'][2]<=left+BODY_WIDTH*scale+.01
                assert row['bbox'][3]<=top+DESC_HEIGHT*scale+.01


@pytest.mark.parametrize('value,expected_lines', [
    ('W1 ENTRY', ['W1 ENTRY']),
    ('U15/1 GF W01 ENTRY', ['U15/1 GF W01','ENTRY']),
    ('BEDROOM EAST FACING WINDOW', ['BEDROOM','EAST FACING','WINDOW']),
])
def test_wrap_one_two_or_three_lines_before_reducing_font(value,expected_lines):
    size,prefix,lines=fit_field('',value,BODY_WIDTH,DESC_HEIGHT,
                              maximum=DESC_SIZE,font_name='Helvetica-Bold',max_lines=DESC_MAX_LINES)
    assert size==DESC_SIZE and lines==expected_lines and prefix==0


def test_only_shrink_when_three_description_lines_are_insufficient():
    value='MASTER BEDROOM NORTH FACING SLIDING DOOR'
    assert len(wrap_complete(value,DESC_SIZE,BODY_WIDTH,'Helvetica-Bold'))>3
    size,prefix,lines=fit_field('',value,BODY_WIDTH,DESC_HEIGHT,
                              maximum=DESC_SIZE,font_name='Helvetica-Bold',max_lines=DESC_MAX_LINES)
    assert size<DESC_SIZE and len(lines)==3
    assert ' '.join(lines)==value
    assert prefix==0


def test_four_full_size_body_lines_fit_and_item_stays_on_one_line(tmp_path):
    src=source(tmp_path/'source.pdf',count=1)
    quote,_,items=read_labels(src)
    diagram=tmp_path/'diagram.png'; Image.new('RGB',(50,50),'white').save(diagram)
    item=replace(items[0],no=123,desc='BEDROOM EAST FACING WINDOW')
    make_labels([item],{123:diagram},tmp_path/'four-lines.pdf',quote)
    with pymupdf.open(tmp_path/'four-lines.pdf') as pdf:
        x,y,w,h=label_box(0)
        scale=min((w-2*PRINT_INSET)/w,(h-2*PRINT_INSET)/h)
        area=pymupdf.Rect(x,y+40,x+190*scale,y+h)
        rows=[line for b in pdf[0].get_text('dict',clip=area)['blocks'] if 'lines' in b
              for line in b['lines']]
        assert len(rows)==4
        assert ''.join(s['text'] for s in rows[0]['spans']).replace(' ','')=='Item:123'
        for idx,row in enumerate(rows):
            for span in row['spans']:
                assert span['font']=='Helvetica-Bold'
                assert span['size']==pytest.approx((ITEM_SIZE if idx==0 else DESC_SIZE)*scale,abs=.001)
        # MuPDF's line boxes include leading, so compare the font's actual
        # ascent/descent bounds to ensure neighboring ink cannot overlap.
        ink=[]
        for row in rows:
            span=row['spans'][0]
            ascent,descent=getAscentDescent(span['font'],span['size'])
            ink.append((span['origin'][1]-ascent,span['origin'][1]-descent))
        assert all(ink[n][1]<ink[n+1][0] for n in range(3))


def test_old_label_cache_does_not_hide_new_layout(tmp_path,monkeypatch):
    import app
    import features.item_labels.service as labels
    monkeypatch.delenv('BLOB_READ_WRITE_TOKEN',raising=False)
    monkeypatch.setattr(app,'JOBS_DIR',tmp_path)
    job='a'*32
    paths=app.get_job_paths(job)
    paths['job_dir'].mkdir()
    paths['input_path'].write_bytes(b'%PDF-input')
    (paths['job_dir']/'item_labels_v3.pdf').write_bytes(b'%PDF-old-layout')
    def generate(src,out,work):
        out.write_bytes(b'%PDF-new-layout'); return {'items':1,'pages':1}
    monkeypatch.setattr(labels,'generate_item_labels',generate)
    client=app.app.test_client()
    assert client.post(f'/api/jobs/{job}/outputs/labels',json={}).status_code==200
    assert client.get('/download-labels/'+job).data==b'%PDF-new-layout'


@pytest.mark.parametrize('failure', ['docket','labels'])
def test_upload_only_and_either_failure_leaves_other_downloadable(tmp_path, monkeypatch, failure):
    import app
    import features.item_labels.service as labels
    monkeypatch.delenv('BLOB_READ_WRITE_TOKEN',raising=False)
    monkeypatch.setattr(app,'JOBS_DIR',tmp_path)
    called=[]
    def docket(paths):
        called.append('docket')
        if failure=='docket': raise ValueError('Docket test failure')
        paths['output_path'].write_bytes(b'%PDF-docket')
    def label(src,out,work):
        called.append('labels')
        if failure=='labels': raise ValueError('Label test failure')
        out.write_bytes(b'%PDF-labels'); return {'items':1,'pages':1}
    monkeypatch.setattr(app,'generate_job',docket)
    monkeypatch.setattr(labels,'generate_item_labels',label)
    client=app.app.test_client()
    response=client.post('/generate',data={'independent_outputs':'1','pdf_file':(io.BytesIO(b'%PDF-input'),'test.pdf')})
    job=response.location.split('/result/')[1].split('?')[0]
    assert not called and client.get(response.location).status_code==200
    success='labels' if failure=='docket' else 'docket'
    for kind in [failure,success]:
        result=client.post(f'/api/jobs/{job}/outputs/{kind}',json={})
        assert result.status_code==(422 if kind==failure else 200)
    route='/download-labels/' if success=='labels' else '/download/'
    assert client.get(route+job).data==f'%PDF-{success}'.encode()
    assert (tmp_path/job/'input.pdf').read_bytes()==b'%PDF-input'
    assert client.get(response.location).status_code==200
    client.post(f'/api/jobs/{job}/outputs/{failure}',json={'retry':True})
    assert client.get(route+job).status_code==200


def test_private_input_and_separate_outputs_survive_another_instance(tmp_path, monkeypatch):
    import app
    import vercel.blob as blob
    import features.item_labels.service as labels
    remote={}
    monkeypatch.setenv('BLOB_READ_WRITE_TOKEN','test-token')
    monkeypatch.setattr(app,'JOBS_DIR',tmp_path/'first')
    def put(path,stream,**kwargs):
        assert kwargs['access']=='private'
        remote[path]=stream.read()
    def download(path,local,**kwargs):
        Path(local).parent.mkdir(parents=True,exist_ok=True)
        Path(local).write_bytes(remote[path])
    monkeypatch.setattr(blob,'put',put)
    monkeypatch.setattr(blob,'download_file',download)
    monkeypatch.setattr(app,'generate_job',lambda paths:paths['output_path'].write_bytes(b'%PDF-docket'))
    def label(src,out,work):
        assert src.read_bytes()==b'%PDF-input'
        out.write_bytes(b'%PDF-labels'); return {}
    monkeypatch.setattr(labels,'generate_item_labels',label)
    client=app.app.test_client()
    response=client.post('/generate',data={'independent_outputs':'1','pdf_file':(io.BytesIO(b'%PDF-input'),'test.pdf')})
    job=response.location.split('/result/')[1].split('?')[0]
    for instance,kind in [('second','labels'),('third','docket')]:
        monkeypatch.setattr(app,'JOBS_DIR',tmp_path/instance)
        assert client.post(f'/api/jobs/{job}/outputs/{kind}',json={}).status_code==200
    monkeypatch.setattr(app,'JOBS_DIR',tmp_path/'fourth')
    assert client.get('/download/'+job).data==b'%PDF-docket'
    assert client.get('/download-labels/'+job).data==b'%PDF-labels'
    assert len(remote)==3
