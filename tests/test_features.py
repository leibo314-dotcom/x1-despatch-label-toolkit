from dataclasses import replace
import io
from pathlib import Path
from types import SimpleNamespace
import pytest
from services.documents import Document, Item, Profile, require_one_quote
from services.jobs import JobStore, FEATURES, run_feature
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
def test_verified_rules_and_wrong_rails(kind,width,left,right,expected):
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


def test_colour_is_independent_and_missing_is_not_pass():
    doc,item=single()
    assert check_colours([doc])['status']=='success'
    assert check_colours([replace(doc,items=(item,replace(item,number=2,colour='White')))])['status']=='warning'
    assert check_colours([replace(doc,items=(replace(item,colour='1 of Standard 2 Colours'),))])['status']=='manual'
    with pytest.raises(ValueError): require_one_quote([doc,replace(doc,quote='another')])
    with pytest.raises(ValueError): calculate_width('single',850,'coupled','sidelight')


@pytest.mark.parametrize('failed',list(FEATURES))
def test_each_failure_and_retry_is_isolated(tmp_path,monkeypatch,failed):
    import services.jobs as jobs
    store=JobStore(tmp_path); job=store.create([('test.pdf',b'%PDF-test')])
    def load(name):
        def run(inputs,output):
            if name==FEATURES[failed][1]: raise RuntimeError('deliberate failure')
            assert inputs[0]['path'].read_bytes()==b'%PDF-test'
            return dict(status='success',summary=name)
        return SimpleNamespace(run=run)
    monkeypatch.setattr(jobs,'execute_feature',lambda feature,inputs,output:load(FEATURES[feature][1]).run(inputs,output))
    for feature in FEATURES: run_feature(store,job,feature)
    before=store.results(job)
    assert before[failed]['status']=='error'
    assert all(v['status']=='success' for k,v in before.items() if k!=failed)
    monkeypatch.setattr(jobs,'execute_feature',lambda *args:dict(status='success',summary='retried'))
    run_feature(store,job,failed)
    after=store.results(job)
    assert all(after[k]==before[k] for k in FEATURES if k!=failed)
    assert store.read(job,'inputs/0.pdf')==b'%PDF-test'


def test_upload_does_not_run_features_and_get_does_not_rerun(tmp_path,monkeypatch):
    import app
    monkeypatch.setattr(app,'store',JobStore(tmp_path))
    monkeypatch.setattr(app,'run_feature',lambda *args:pytest.fail('GET/upload ran feature'))
    client=app.app.test_client()
    response=client.post('/generate',data={'pdf_file':(io.BytesIO(b'%PDF-test'),'test.pdf')})
    assert response.status_code==302
    job=response.location.rsplit('/',1)[-1]
    assert client.get(response.location).status_code==200
    assert all(v['status']=='pending' for v in app.store.results(job).values())
    assert client.get('/download/'+job).status_code==404
    assert client.post(f'/api/jobs/{job}/unknown/run').status_code==404
    assert client.get('/result/invalid').status_code==404
    assert client.post(f'/jobs/{job}/delete').status_code==302
    assert client.get(response.location).status_code==404


def test_remote_store_survives_new_instances(tmp_path,monkeypatch):
    import vercel.blob as blob
    remote={}
    monkeypatch.setattr(blob,'put',lambda path,body,**kwargs:remote.__setitem__(path,body))
    monkeypatch.setattr(blob,'get',lambda path,**kwargs:SimpleNamespace(content=remote[path]))
    first=JobStore(tmp_path/'a',True); second=JobStore(tmp_path/'b',True)
    job=first.create([('test.pdf',b'%PDF-test')])
    second.write_json(job,'colour/result.json',{'status':'manual'})
    assert first.json(job,'colour/result.json')['status']=='manual'
    assert second.read(job,'inputs/0.pdf')==b'%PDF-test'


def test_blob_upload_uses_same_manifest(tmp_path,monkeypatch):
    import app
    import vercel.blob as blob
    remote={}; removed=[]
    monkeypatch.setattr(app,'store',JobStore(tmp_path,True))
    monkeypatch.setattr(blob,'put',lambda path,body,**kwargs:remote.__setitem__(path,body))
    monkeypatch.setattr(blob,'get',lambda path,**kwargs:SimpleNamespace(content=remote.get(path,b'%PDF-test')))
    monkeypatch.setattr(blob,'delete',lambda paths:removed.extend(paths))
    client=app.app.test_client()
    files=[{'blob_pathname':'x1-inputs/'+'a'*32+'-test.pdf','source_name':'test.pdf'}]
    response=client.post('/generate-from-blob',json={'files':files})
    assert response.status_code==200
    job=response.json['result_url'].rsplit('/',1)[-1]
    assert app.store.json(job,'manifest.json')['inputs'][0]['name']=='test.pdf'
    assert len(removed)==1
    assert client.post('/generate-from-blob',json={'files':[{'blob_pathname':'../../secret'}]}).status_code==400
