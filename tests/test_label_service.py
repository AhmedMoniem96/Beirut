from PIL import Image
import pytest
import beirut_pos.apps.jewelry.label_printing.service as service
from beirut_pos.apps.jewelry.label_printing import LabelData
from beirut_pos.apps.jewelry.label_printing.transport import Submission, LabelTransportError

DATA=LabelData('عقد عقيق اسود','2021100101','700.00 LE')
def test_happy_path_exact_boundaries(monkeypatch):
    image=Image.new('1',(304,200)); result=Submission(True,'RP3xx Series 200DPI TSPL',1)
    seen={}
    def render(value): seen['data']=value; return image
    def transport(value,name,copies): seen.update(image=value,name=name,copies=copies); return result
    monkeypatch.setattr(service,'render_label',render); monkeypatch.setattr(service,'print_image',transport)
    assert service.print_label(DATA,'RP3xx Series 200DPI TSPL') is result
    assert seen['data'] is DATA and seen['image'] is image and seen['name']=='RP3xx Series 200DPI TSPL' and seen['copies']==1

def test_copies_unchanged(monkeypatch):
    image=Image.new('1',(304,200)); calls=[]
    monkeypatch.setattr(service,'render_label',lambda x:image); monkeypatch.setattr(service,'print_image',lambda *a:calls.append(a) or Submission(True,'q',2))
    service.print_label(DATA,'q',2); assert calls==[(image,'q',2)]

def test_renderer_failure_transport_not_called(monkeypatch):
    error=ValueError('bad label'); called=[]
    monkeypatch.setattr(service,'render_label',lambda x: (_ for _ in ()).throw(error)); monkeypatch.setattr(service,'print_image',lambda *a:called.append(a))
    with pytest.raises(ValueError) as exc: service.print_label(DATA,'q')
    assert exc.value is error and not called

def test_transport_failure_propagates(monkeypatch):
    error=LabelTransportError('offline'); image=Image.new('1',(304,200)); called=[]
    monkeypatch.setattr(service,'render_label',lambda x:called.append(x) or image); monkeypatch.setattr(service,'print_image',lambda *a: (_ for _ in ()).throw(error))
    with pytest.raises(LabelTransportError) as exc: service.print_label(DATA,'q',2)
    assert exc.value is error and called==[DATA]

def test_invalid_data(monkeypatch):
    with pytest.raises(TypeError): service.print_label(object(),'q')
