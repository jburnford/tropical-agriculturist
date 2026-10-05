# Contact sheet: autocontrast-enhanced top half of listed pages, 4 per row, for eyeballing.
import sys, glob, pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageDraw
pdfs={}
for f in glob.glob("chunks/chunk_*.tsv"):
    for l in open(f):
        t,p=l.split("\t")[:2]; pdfs[t]=p
items=[a.split(":") for a in sys.argv[2:]]
tiles=[]
for tag,pg in items:
    t=[k for k in pdfs if k.startswith(tag)][0]
    doc=pdfium.PdfDocument(pdfs[t]); im=doc[int(pg)].render(scale=1.2).to_pil().convert("L")
    w,h=im.size; im=ImageOps.autocontrast(im.crop((0,0,w,h//2)),cutoff=(1,1)).resize((520,int(520*(h//2)/w)))
    d=ImageDraw.Draw(im); d.rectangle((0,0,200,22),fill=255); d.text((4,4),f"{tag} p{pg}",fill=0)
    tiles.append(im)
W=520*4; H=max(t.size[1] for t in tiles); rows=(len(tiles)+3)//4
S=Image.new("L",(W,H*rows),255)
for i,t in enumerate(tiles): S.paste(t,((i%4)*520,(i//4)*H))
S.save(sys.argv[1])
