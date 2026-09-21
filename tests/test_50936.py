"""Optional real-document regression. Supply X1_SAMPLE_50936 to run."""
import os
from pathlib import Path
from dataclasses import replace
import pytest
from features.door_width.service import run
from services.documents import read_document

@pytest.fixture(scope='module')
def sample():
    path=Path(os.environ.get('X1_SAMPLE_50936','missing-sample.pdf'))
    if not path.is_file(): pytest.skip('Set X1_SAMPLE_50936 to the supplied Assembly PDF')
    return path

def test_actual_sample_and_continuations(sample,tmp_path):
    doc=read_document(sample,sample.name)
    assert len(doc.items)==10
    assert doc.items[4].pages==(5,6)
    assert doc.items[9].pages==(11,12)
    result=run([{'path':sample,'name':sample.name}],tmp_path)
    assert result['counts']==dict(total=10,passed=10,mismatch=0,manual=0,unsupported=0)
    assert [i['expected_v661'] for i in result['items']]==[646,664,682,626,606,636,695,704,626,616]
    assert not result['details']

def test_duplicate_documents_are_manual(sample,tmp_path):
    result=run([{'path':sample,'name':sample.name}]*2,tmp_path)
    assert result['counts']['manual']==10

def test_screw_number_is_not_an_extra_delivery_item(sample):
    from features.delivery.renderer import parse_items
    assert [i.no for i in parse_items(sample)]==list(range(1,11))
