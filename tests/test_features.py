from dataclasses import replace
import io
from pathlib import Path
import pytest
from services.documents import Document, Item, Profile, require_one_quote
from features.door_width.rules import compare_widths, calculate_width
from features.door_width.service import check_item
from features.colour.service import check_colours

@pytest.mark.parametrize('kind,width,left,right,expected', [
    ('single',850,'frame','frame',646),('single',850,'sidelight','frame',664),
    ('single',850,'sidelight','sidelight',682),('single',850,'frame','coupled',626),
    ('single',850,'coupled','coupled',606),('french',1600,'frame','frame',636),
    ('french',1700,'frame','sidelight',695),('french',1700,'sidelight','sidelight',704),
    ('french',1600,'coupled','frame',626),('french',1600,'coupled','coupled',616),
])
def test_width_rules(kind,width,left,right,expected):
    assert compare_widths(kind,width,left,right,[expected])['status']=='passed'
    assert compare_widths(kind,width,left,right,[expected,expected+2])['status']=='mismatch'
    assert compare_widths(kind,width,left,right,[expected-2])['differences']==[-2]
    assert compare_widths(kind,width,left,right,[])['status']=='manual'

def single():
    item=Item(1,'door','Hinged Dr (TL40)','Black',1,(1,),
              (Profile('V650',888,2,1),Profile('V660',1900,2,1),Profile('V661',646,2,1)),
              'Trim Size 2030 x 880')
    return Document(Path('test.pdf'),'test.pdf','50936','assembly',(item,)),item

def drawing(*args):
    return dict(door_indices=[0],section_widths=[850],total_width=850,door_width=850)

@pytest.mark.parametrize('change,status', [
    ({'frame':'Hinged Dr (other)'},'unsupported'),({'quantity':2},'manual'),
    ({'profiles':()},'manual'),({'text':'Trim Size 2030 x 999'},'manual'),
])
def test_incomplete_evidence_never_passes(change,status):
    doc,item=single()
    assert check_item(doc,replace(item,**change),drawing)['status']==status

def test_ocr_failure_is_manual():
    from features.door_width.drawing import DrawingUnclear
    doc,item=single()
    def unclear(*args): raise DrawingUnclear('Low confidence')
    assert check_item(doc,item,unclear)['status']=='manual'
    assert check_item(replace(doc,kind='schedule'),item,drawing)['status']=='manual'

def test_unequal_french_is_unsupported():
    doc,item=single()
    item=replace(item,text='Trim Size 2030 x 1630',profiles=(Profile('V650',1600,2,1),Profile('V660',1900,4,1),Profile('V661',636,4,1),Profile('V220',1900,1,1)))
    unequal=lambda *args:dict(door_indices=[0,1],section_widths=[900,700],total_width=1600,door_width=1600)
    assert check_item(doc,item,unequal)['status']=='unsupported'

def test_colour_consistency_and_missing_data():
    doc,item=single()
    assert check_colours([doc])['colour']=='Black'
    assert check_colours([doc])['status']=='success'
    assert check_colours([replace(doc,items=(item,replace(item,number=2,colour='White')))])['status']=='warning'
    assert check_colours([replace(doc,items=(replace(item,colour=''),))])['status']=='manual'
    # The tool checks consistency of the recorded colour, not finish certification.
    r=check_colours([replace(doc,items=(replace(item,colour='1 of Standard 2 Colours'),))])
    assert r['status']=='success' and r['colour']=='1 of Standard 2 Colours'
    with pytest.raises(ValueError): require_one_quote([doc,replace(doc,quote='another')])
    with pytest.raises(ValueError): calculate_width('single',850,'coupled','sidelight')

@pytest.mark.parametrize('failed',['colour','door_width'])
def test_checks_parse_once_and_isolate_failures(tmp_path,monkeypatch,failed):
    import services.documents as documents
    import features.colour.service as colour
    import features.door_width.service as width
    from services.checks import run_checks
    calls=[];doc,_=single()
    monkeypatch.setattr(documents,'read_document',lambda *args:calls.append(1) or doc)
    def result(name):
        def check(docs):
            assert docs==(doc,)
            if name==failed: raise RuntimeError('deliberate failure')
            return {'status':'success'}
        return check
    monkeypatch.setattr(colour,'check_colours',result('colour'))
    monkeypatch.setattr(width,'check_documents',result('door_width'))
    results=run_checks(tmp_path/'source.pdf',tmp_path)
    assert calls==[1]
    assert results[failed]['status']=='manual'
    assert results['colour' if failed=='door_width' else 'door_width']['status']=='success'
    assert run_checks(tmp_path/'source.pdf',tmp_path)==results
    assert calls==[1]
    run_checks(tmp_path/'source.pdf',tmp_path,True)
    assert calls==[1,1]

def test_delivery_never_calls_checks_and_download_survives_failure(tmp_path,monkeypatch):
    import app
    monkeypatch.setattr(app,'JOBS_DIR',tmp_path)
    def generate(paths): paths['output_path'].write_bytes(b'%PDF-docket')
    monkeypatch.setattr(app,'generate_job',generate)
    monkeypatch.setattr(app,'run_checks',lambda *args:pytest.fail('Delivery called checks'))
    client=app.app.test_client()
    response=client.post('/generate',data={'pdf_file':(io.BytesIO(b'%PDF-input'),'test.pdf')})
    assert response.status_code==302
    job=response.location.split('/result/')[1].split('?')[0]
    assert client.get(response.location).status_code==200
    assert client.get('/download/'+job).data==b'%PDF-docket'
    monkeypatch.setattr(app,'run_checks',lambda *args:{'colour':{'status':'manual'},'door_width':{'status':'manual'}})
    assert client.post(f'/api/jobs/{job}/checks').status_code==200
    assert client.get('/download/'+job).data==b'%PDF-docket'

def test_blob_delivery_keeps_original_path(tmp_path,monkeypatch):
    import app
    import vercel.blob as blob
    monkeypatch.setattr(app,'JOBS_DIR',tmp_path)
    monkeypatch.setenv('BLOB_READ_WRITE_TOKEN','test-token')
    monkeypatch.setattr(blob,'download_file',lambda path,local,**kwargs:Path(local).write_bytes(b'%PDF-input'))
    deleted=[];monkeypatch.setattr(blob,'delete',deleted.append)
    monkeypatch.setattr(app,'generate_job',lambda paths:paths['output_path'].write_bytes(b'%PDF-docket'))
    monkeypatch.setattr(app,'run_checks',lambda *args:pytest.fail('Blob delivery called checks'))
    client=app.app.test_client()
    response=client.post('/generate-from-blob',json={'blob_pathname':'x1-inputs/'+'a'*32+'-test.pdf','source_name':'test.pdf'})
    assert response.status_code==200
    assert client.get(response.json['result_url']).status_code==200
    assert len(deleted)==1
