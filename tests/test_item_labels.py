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
from features.item_labels.render import label_box, fit_field, make_labels
from features.item_labels.source import read_labels
from features.item_labels.service import generate_item_labels


def source(path, count=2, assembly=False):
    c = canvas.Canvas(str(path), pagesize=A4)
    for number in range(1, count+1):
        c.setFont('Helvetica', 10)
        c.drawString(25, 815, 'Assembly Drawing' if assembly else 'Schedule')
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
                assert (rect.x0,rect.y0,rect.width)==pytest.approx((x,y,w),abs=.001)
        preferences=int(pdf.xref_get_key(pdf.pdf_catalog(),'ViewerPreferences')[1].split()[0])
        assert pdf.xref_get_key(preferences,'PrintScaling')==('name','/None')


def test_long_values_shrink_and_keep_every_character(tmp_path):
    values=['Master bedroom extra long description at rear of building',
            'A'*90, 'Cill Support: 00470 - 20mm Sill Support for extra wide frame']
    for value in values:
        size,prefix,lines=fit_field('Desc:',value,179,14)
        assert size<13.4
        assert ''.join(''.join(lines).split())==''.join(value.split())
        assert len(lines)*size*1.06<=14
    src=source(tmp_path/'source.pdf', count=1)
    quote,_,items=read_labels(src)
    item=replace(items[0],desc=values[0],colour=values[1],flashing=values[2],wanz=values[2])
    diagram=tmp_path/'diagram.png'; Image.new('RGB',(50,50),'white').save(diagram)
    make_labels([item],{1:diagram},tmp_path/'long.pdf',quote)
    with pymupdf.open(tmp_path/'long.pdf') as pdf:
        text=''.join(pdf[0].get_text().split())
        for value in values: assert ''.join(value.split()) in text
        assert '...' not in text


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
