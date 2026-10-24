"""Local OCR with source-pixel symbol boxes, never synthetic PDF font metrics."""
from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image, ImageOps


def _runs(values, gap):
    runs=[]
    for n in values:
        n=int(n)
        if not runs or n-runs[-1][1]>gap:runs.append([n,n])
        else:runs[-1][1]=n
    return runs


def line_regions(gray):
    """Projection is an extra pass for separated printed lines, not a coverage filter."""
    data=np.asarray(gray)
    hist=np.bincount(data.ravel(),minlength=256).astype(float)
    weight=np.cumsum(hist);moment=np.cumsum(hist*np.arange(256))
    between=(moment[-1]*weight-moment*weight[-1])**2/(weight*(weight[-1]-weight)+1)
    threshold=max(40,min(210,int(np.argmax(between))))
    mask=data<=threshold
    bands=_runs(np.flatnonzero(mask.sum(axis=1)>max(2,gray.width*.001)),4)
    regions=[]
    for y0,y1 in bands:
        height=y1-y0+1
        if not 8<=height<=min(240,gray.height*.35):continue
        xs=np.flatnonzero(mask[y0:y1+1].sum(axis=0))
        for x0,x1 in _runs(xs,max(60,height*4)):
            if x1-x0<height:continue
            # A large solid picture / border is not a line of printed characters.
            density=float(mask[y0:y1+1,x0:x1+1].mean())
            if not .025<=density<=.65:continue
            regions.append((max(0,x0-3),max(0,y0-3),min(gray.width,x1+4),min(gray.height,y1+4)))
    return regions if len(regions)<=96 else []


def _recognize(api, frame, rect, original_size, psm):
    from tesserocr import RIL
    api.SetPageSegMode(psm)
    x0,y0,x1,y1=rect
    sx,sy=(x1-x0)/frame.width,(y1-y0)/frame.height
    border=12
    api.SetImage(ImageOps.expand(frame,border=border,fill=255));api.Recognize()
    ri=api.GetIterator()
    if ri is None:return []
    lines=[];line=None
    while True:
        if line is None or ri.IsAtBeginningOf(RIL.TEXTLINE):
            line={'text':'','boxes':[],'confidences':[]}
            lines.append(line)
        symbol=ri.GetUTF8Text(RIL.SYMBOL) or '';box=ri.BoundingBox(RIL.SYMBOL)
        if symbol and box:
            # RIL.TEXTLINE inserts artificial spaces between Korean word-iterator entries.
            # BlanksBeforeWord preserves the engine's actual spacing (e.g. 김민수, not 김 민 수).
            if line['text'] and ri.IsAtBeginningOf(RIL.WORD) and ri.BlanksBeforeWord()>0:
                line['text']+=' ';line['boxes'].append(None);line['confidences'].append(None)
            mapped=[max(0,min(original_size[0],x0+(box[0]-border)*sx)),max(0,min(original_size[1],y0+(box[1]-border)*sy)),
                    max(0,min(original_size[0],x0+(box[2]-border)*sx)),max(0,min(original_size[1],y0+(box[3]-border)*sy))]
            confidence=float(ri.Confidence(RIL.SYMBOL))
            line['text']+=symbol;line['boxes'].extend([mapped]*len(symbol));line['confidences'].extend([confidence]*len(symbol))
        if not ri.Next(RIL.SYMBOL):break
    result=[]
    for line in lines:
        if not line['text'].strip():continue
        # Never invent character geometry when the text iterator cannot align it.
        if any(b is None and not c.isspace() for c,b in zip(line['text'],line['boxes'])):
            raise ValueError('OCR symbol alignment failed')
        for i,b in enumerate(line['boxes']):
            if b is not None:continue
            previous=next((v for v in reversed(line['boxes'][:i]) if v),None)
            following=next((v for v in line['boxes'][i+1:] if v),None)
            edge=previous or following
            line['boxes'][i]=[edge[2],edge[1],edge[2],edge[3]]
        result.append(line)
    return result


def _inside(box, rect):
    x0,y0,x1,y1=box;a,b,c,d=rect
    area=max(0,x1-x0)*max(0,y1-y0)
    overlap=max(0,min(x1,c)-max(x0,a))*max(0,min(y1,d)-max(y0,b))
    return area>0 and (overlap/area>.8 or a<=(x0+x1)/2<=c and b<=(y0+y1)/2<=d)


def read_image(image, tessdata):
    from tesserocr import PyTessBaseAPI, PSM
    gray=ImageOps.grayscale(image)
    if np.median(np.asarray(gray))<128:gray=ImageOps.invert(gray)
    gray=ImageOps.autocontrast(gray,cutoff=.5)
    with PyTessBaseAPI(path=str(Path(tessdata)),lang='kor+eng',psm=PSM.SPARSE_TEXT) as api:
        # Full-image pass retains text outside the lines used for the precision pass.
        baseline=_recognize(api,gray,(0,0,*gray.size),gray.size,PSM.SPARSE_TEXT)
        result=[];covered=[]
        for rect in line_regions(gray):
            crop=gray.crop(rect);scale=max(1,min(1.6,30/crop.height)) if crop.height<24 else min(1,48/crop.height)
            crop=crop.resize((max(1,round(crop.width*scale)),max(1,round(crop.height*scale))),Image.Resampling.LANCZOS)
            lines=_recognize(api,crop,rect,gray.size,PSM.SINGLE_LINE)
            if lines:result.extend(lines);covered.append(rect)
        for line in baseline:
            # Keep runs not covered by a successful precision pass; do not silently discard small text.
            start=None
            keep=[not any(_inside(b,r) for r in covered) for b in line['boxes']]
            for i,k in enumerate(keep+[False]):
                if k and start is None:start=i
                elif not k and start is not None:
                    if line['text'][start:i].strip():result.append({key:value[start:i] for key,value in line.items()})
                    start=None
        result.sort(key=lambda line:(min(b[1] for b in line['boxes']),min(b[0] for b in line['boxes'])))
        return result
