from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from .errors import LabelRenderingError
from .geometry import *
FONT_PATH=Path(__file__).resolve().parents[3]/'assets/fonts/NotoNaskhArabic-Regular.ttf'
_PATTERNS=('212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112').split()
def _shape(s): return get_display(arabic_reshaper.reshape(s))
def encode_code128(value):
    if not value or any(ord(c)<32 or ord(c)>126 for c in value): raise LabelRenderingError('Code128 requires printable ASCII')
    if value.isdigit() and len(value)%2==0:
        subset='C'; vals=[105]+[int(value[i:i+2]) for i in range(0,len(value),2)]
    else:
        subset='B'; vals=[104]+[ord(c)-32 for c in value]
    checksum=(vals[0]+sum(i*v for i,v in enumerate(vals[1:],1)))%103
    codes=vals+[checksum,106]; bits=[]
    for code in codes:
        for i,w in enumerate(map(int,_PATTERNS[code])): bits.extend([i%2]*w)
    return subset,codes,checksum,bits
def barcode_geometry(value,region=BARCODE_REGION):
    subset,codes,checksum,bits=encode_code128(value); modules=len(bits); usable=region.width-2*QUIET_ZONE_MODULES
    width=usable//modules
    if width<1: raise LabelRenderingError('Barcode cannot fit with integer modules and quiet zones')
    total=modules*width+2*QUIET_ZONE_MODULES*width; x=region.x+(region.width-total)//2
    return subset,codes,checksum,bits,width,(x,region.y,total,region.height)
def _fit(draw,text,region,lo,hi):
    shaped=_shape(text)
    for size in range(hi,lo-1,-1):
        f=ImageFont.truetype(str(FONT_PATH),size); b=draw.textbbox((0,0),shaped,font=f)
        if b[2]-b[0]<=region.width and b[3]-b[1]<=region.height:return shaped,f
    raise LabelRenderingError('Text cannot fit assigned region')
def render_label(data):
    if not FONT_PATH.is_file(): raise LabelRenderingError(f'Bundled font not found: {FONT_PATH}')
    im=Image.new('1',(WIDTH,HEIGHT),1); d=ImageDraw.Draw(im)
    shaped,f=_fit(d,data.product_name,PRODUCT_REGION,14,32); b=d.textbbox((0,0),shaped,font=f)
    d.text((PRODUCT_REGION.x+(PRODUCT_REGION.width-(b[2]-b[0]))//2,PRODUCT_REGION.y+(PRODUCT_REGION.height-(b[3]-b[1]))//2-b[1]),shaped,font=f,fill=0)
    subset,codes,checksum,bits,mw,(x,y,total,h)=barcode_geometry(data.barcode); q=QUIET_ZONE_MODULES*mw; start=x+q
    for i,v in enumerate(bits):
        if v==0:d.rectangle((start+i*mw,y,start+(i+1)*mw-1,y+h-1),fill=0)
    hf=ImageFont.truetype(str(FONT_PATH),17); hb=d.textbbox((0,0),data.barcode,font=hf)
    d.text((HUMAN_REGION.x+(HUMAN_REGION.width-(hb[2]-hb[0]))//2,HUMAN_REGION.y+(HUMAN_REGION.height-(hb[3]-hb[1]))//2-hb[1]),data.barcode,font=hf,fill=0)
    price=str(data.price)
    for ps in range(20,11,-1):
        pf=ImageFont.truetype(str(FONT_PATH),ps); pb=d.textbbox((0,0),price,font=pf)
        if pb[2]-pb[0]<=PRICE_REGION.width and pb[3]-pb[1]<=PRICE_REGION.height:break
    else: raise LabelRenderingError('Price cannot fit assigned region')
    d.text((PRICE_REGION.x+(PRICE_REGION.width-(pb[2]-pb[0]))//2,PRICE_REGION.y+(PRICE_REGION.height-(pb[3]-pb[1]))//2-pb[1]),price,font=pf,fill=0)
    return im
def save_preview(data,path):
    im=render_label(data); Path(path).parent.mkdir(parents=True,exist_ok=True); im.save(path,'PNG'); return path
