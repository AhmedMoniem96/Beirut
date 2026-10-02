import sys, types
from PIL import Image
import pytest
from beirut_pos.apps.jewelry.label_printing.transport import print_image,LabelTransportError

def img(): return Image.new('1',(304,200),1)
class FakeDC:
 def __init__(self,fail=None): self.fail=fail or ''; self.calls=[]
 def CreatePrinterDC(self,n): self.calls.append(('CreatePrinterDC',n)); self._fail('createdc')
 def _fail(self,name):
  if self.fail==name: raise RuntimeError(name)
 def GetDeviceCaps(self,c): return 1000
 def StartDoc(self,n): self.calls.append(('StartDoc',n)); self._fail('startdoc')
 def StartPage(self): self.calls.append(('StartPage',)); self._fail('startpage')
 def EndPage(self): self.calls.append(('EndPage',)); self._fail('endpage')
 def EndDoc(self): self.calls.append(('EndDoc',)); self._fail('enddoc')
 def AbortDoc(self): self.calls.append(('AbortDoc',))
 def DeleteDC(self): self.calls.append(('DeleteDC',))
 def GetHandleOutput(self): return 1
class Dib:
 dc=None; fail=False
 def __init__(self,i): pass
 def draw(self,h,r): self.dc.calls.append(('draw',r));

def install(monkey,fail=''):
 d=FakeDC(fail); monkey.setattr(sys,'platform','win32'); Dib.dc=d
 monkey.setitem(sys.modules,'win32con',types.SimpleNamespace(HORZRES=1,VERTRES=2,PHYSICALOFFSETX=3,PHYSICALOFFSETY=4))
 monkey.setitem(sys.modules,'win32ui',types.SimpleNamespace(CreateDC=lambda:d))
 monkey.setitem(sys.modules,'PIL.ImageWin',types.SimpleNamespace(Dib=lambda i:Dib(i)))
 return d

def test_non_windows():
 with pytest.raises(LabelTransportError,match='only available'): print_image(img(),'x')
@pytest.mark.parametrize('fail', ['draw','startpage','endpage','enddoc','createdc'])
def test_failure_paths(monkeypatch,fail):
 d=install(monkeypatch,fail)
 if fail=='draw':
  old=Dib.draw
  def broken(self,h,r): d.calls.append(('draw',r)); raise RuntimeError('draw')
  monkeypatch.setattr(Dib,'draw',broken)
 with pytest.raises(LabelTransportError): print_image(img(),'Exact Queue')
 assert ('DeleteDC',) in d.calls
 if fail=='createdc': assert not any(x[0] in ('StartDoc','StartPage','draw','EndPage','EndDoc') for x in d.calls)
 else: assert ('AbortDoc',) in d.calls
 assert ('EndDoc','BeirutPOS Jewelry Label') not in d.calls if fail in ('draw','startpage','endpage','enddoc') else True

def test_success_and_copies(monkeypatch):
 d=install(monkeypatch); r=print_image(img(),'Exact Queue',2)
 assert r.physical_print_confirmed is False
 assert ('CreatePrinterDC','Exact Queue') in d.calls
 assert sum(x[0]=='StartDoc' for x in d.calls)==2 and sum(x[0]=='EndDoc' for x in d.calls)==2
 assert ('draw',(0,0,304,200)) in d.calls and d.calls[-1]==('DeleteDC',)
