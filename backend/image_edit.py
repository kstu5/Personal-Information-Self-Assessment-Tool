"""Opaque pixel removal and local text replacement for standalone document images.

The original candidate rectangle is erased in full, including uncertain OCR bounds.
Ink measurements affect only replacement layout, never reduce the removal region.
Preview and export call the same renderer. No inpainting or network is used.
"""
from pathlib import Path
from functools import lru_cache
import math
import unicodedata

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


class ImageEditError(ValueError):
    pass


def pixel_box(box, size):
    if not isinstance(box, (list, tuple)) or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
        raise ImageEditError('이미지 수정 위치가 올바르지 않습니다.')
    if not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]):
        raise ImageEditError('이미지 수정 영역이 범위를 벗어났습니다.')
    return math.floor(box[0]), math.floor(box[1]), math.ceil(box[2]), math.ceil(box[3])


def validate_text(text):
    if not isinstance(text, str) or len(text) > 80 or any(unicodedata.category(c) in {'Cc','Cs','Zl','Zp'} for c in text):
        raise ImageEditError('이미지 수정 문구는 줄바꿈 없이 80자 이하로 입력해 주세요.')


def font_path():
    paths = [Path('C:/Windows/Fonts/malgun.ttf'), Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
             Path('/usr/share/fonts/truetype/nanum/NanumGothic.ttf')]
    for path in paths:
        if path.is_file():
            return str(path)
    raise ImageEditError('이미지 문구 표시에 필요한 한국어 글꼴을 찾지 못했습니다.')


@lru_cache(maxsize=128)
def _font(path, size):
    return ImageFont.truetype(path,size)


@lru_cache(maxsize=4096)
def _supports(path, char):
    if char.isspace() or char=='\u200d' or 0xfe00<=ord(char)<=0xfe0f:
        return True
    font=_font(path,32)
    glyph,missing=font.getmask(char),font.getmask(chr(0x10ffff))
    return glyph.size!=missing.size or bytes(glyph)!=bytes(missing)


def _runs(text, size):
    """Keep Korean/Latin kerning; use local symbol fonts only for missing glyphs."""
    paths=[font_path()]+[str(p) for p in (
        Path('C:/Windows/Fonts/seguisym.ttf'),Path('C:/Windows/Fonts/seguiemj.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf')) if p.is_file()]
    clusters=[]
    for char in text:
        if clusters and (unicodedata.combining(char) or char=='\u200d' or clusters[-1].endswith('\u200d') or 0xfe00<=ord(char)<=0xfe0f):
            clusters[-1]+=char
        else:clusters.append(char)
    runs=[]
    for cluster in clusters:
        path=next((p for p in paths if all(_supports(p,c) for c in cluster)),None)
        if path is None:
            raise ImageEditError('표시할 수 없는 문자가 있습니다. 다른 기호나 일반 문자로 바꿔 주세요.')
        try:font=_font(path,size)
        except OSError:
            raise ImageEditError('이 기호를 현재 글자 크기로 표시할 수 없습니다. 다른 기호로 바꿔 주세요.')
        if runs and runs[-1][0]==path:runs[-1][1]+=cluster
        else:runs.append([path,cluster,font])
    return runs


def _typography(ink_box, original):
    # The reference is the original text, never the replacement's width or symbols.
    height=max(4,ink_box[3]-ink_box[1]);reference=original or '가'
    path=font_path()
    def score(size):
        b=_font(path,size).getbbox(reference,anchor='ls')
        return (abs(b[3]-b[1]-height),abs(b[2]-b[0]-(ink_box[2]-ink_box[0])) if original else size)
    size=min(range(max(6,round(height*.7)),min(512,max(10,round(height*2.2)))+1),key=score)
    bounds=_font(path,size).getbbox(reference,anchor='ls')
    return size,ink_box[0]-bounds[0],ink_box[3]-bounds[3]


def _text_layout(text, size, x, baseline):
    runs=_runs(text,size);position=0;bounds=[];placed=[]
    for _,value,font in runs:
        b=font.getbbox(value,anchor='ls')
        bounds.append((x+position+b[0],baseline+b[1],x+position+b[2],baseline+b[3]))
        placed.append((x+position,baseline,value,font))
        position+=font.getlength(value)
    box=(math.floor(min(b[0] for b in bounds))-1,math.floor(min(b[1] for b in bounds))-1,
         math.ceil(max(b[2] for b in bounds))+1,math.ceil(max(b[3] for b in bounds))+1)
    return placed,box


def _check_space(source, box, text_box, background, occupied):
    """Expand into blank same-line paper only; never erase adjacent text or rules."""
    x0,y0,x1,y1=text_box
    if x0<0 or y0<0 or x1>source.width or y1>source.height:
        raise ImageEditError('문구가 이미지 밖으로 나갑니다. 글자 크기는 유지하므로 문구를 짧게 입력해 주세요.')
    crop=np.asarray(source)[y0:y1,x0:x1]
    outside=np.ones(crop.shape[:2],dtype=bool)
    a,b,c,d=max(x0,box[0]),max(y0,box[1]),min(x1,box[2]),min(y1,box[3])
    if a<c and b<d:outside[b-y0:d-y0,a-x0:c-x0]=False
    if np.any((np.max(np.abs(crop.astype(int)-np.array(background)),axis=2)>24)&outside):
        raise ImageEditError('같은 줄의 빈 공간이 부족합니다. 주변 글자·표 선을 보존하려면 문구를 짧게 입력해 주세요.')
    if any(max(x0,p[0])<min(x1,p[2]) and max(y0,p[1])<min(y1,p[3]) for p in occupied):
        raise ImageEditError('새 문구끼리 겹칩니다. 문구를 짧게 입력하거나 선택을 조정해 주세요.')


def _layout(source, box):
    """Estimate flat paper color and glyph bounds; reconstruct only crossing rules.

    Rule colors come from outside the removed rectangle. Inside pixels are never
    copied back. Layout may be approximate on textured backgrounds and handwriting.
    """
    data = np.asarray(source)
    x0, y0, x1, y1 = box
    pad = max(3, min(12, (y1-y0)//3))
    strips = [data[max(0,y0-pad):y0, x0:x1], data[y1:min(source.height,y1+pad), x0:x1],
              data[y0:y1, max(0,x0-pad):x0], data[y0:y1, x1:min(source.width,x1+pad)]]
    samples = [s.reshape(-1,3) for s in strips if s.size]
    samples = np.concatenate(samples) if samples else data[y0:y1,x0:x1].reshape(-1,3)
    # The upper half excludes dark ink and table borders from the paper estimate.
    luminance = samples.mean(axis=1)
    paper = samples[luminance >= np.median(luminance)]
    background = tuple(int(v) for v in np.median(paper,axis=0))
    crop = data[y0:y1,x0:x1]
    contrast = np.max(np.abs(crop.astype(int)-np.array(background)),axis=2)
    ink = contrast > 45
    horizontal, vertical = [], []
    if x0 >= 4 and x1+4 <= source.width:
        left = data[y0:y1,x0-4:x0].mean(axis=1)
        right = data[y0:y1,x1:x1+4].mean(axis=1)
        rows = (np.max(np.abs(left-right),axis=1)<22) & (left.mean(axis=1)<np.mean(background)-45)
        for y in np.flatnonzero(rows):
            horizontal.append((int(y),tuple(int(v) for v in (left[y]+right[y])/2)))
            ink[y,:] = False
    if y0 >= 4 and y1+4 <= source.height:
        top = data[y0-4:y0,x0:x1].mean(axis=0)
        bottom = data[y1:y1+4,x0:x1].mean(axis=0)
        columns = (np.max(np.abs(top-bottom),axis=1)<22) & (top.mean(axis=1)<np.mean(background)-45)
        for x in np.flatnonzero(columns):
            vertical.append((int(x),tuple(int(v) for v in (top[x]+bottom[x])/2)))
            ink[:,x] = False
    ys, xs = np.nonzero(ink)
    if len(ys):
        # Ignore isolated JPEG speckles for typography only, not for erasure.
        row_counts = ink.sum(axis=1)
        active = np.flatnonzero(row_counts >= max(2,(x1-x0)*.025))
        a, b = (int(active[0]), int(active[-1])+1) if len(active) else (int(ys.min()),int(ys.max())+1)
        ink_box = [x0+int(xs.min()),y0+a,x0+int(xs.max())+1,y0+b]
        # Edge antialias pixels must not turn black source lettering into grey.
        cores=ink & (contrast>=np.percentile(contrast[ink],80))
        foreground = tuple(int(v) for v in np.median(crop[cores],axis=0))
    else:
        ink_box, foreground = list(box), (30,35,40)
    return background, foreground, ink_box, horizontal, vertical


def render_image(source, replacements, regions, *, strict=True):
    if source.width*source.height > 20_000_000:
        raise ImageEditError('이미지는 2천만 화소 이하로 처리해 주세요.')
    if len(replacements)>6000 or len(regions)>20000:
        raise ImageEditError('이미지 수정 영역이 너무 많습니다.')
    source = source.convert('RGB')
    # A fresh image has no EXIF, PNG text chunks, original thumbnail, or layers.
    output = Image.fromarray(np.array(source))
    draw = ImageDraw.Draw(output)
    plans = [];occupied=[]
    boxes=[pixel_box(item['box'],source.size) for item in replacements]
    conflicts=set()
    for i,box in enumerate(boxes):
        for j in range(i):
            other=boxes[j]
            if max(box[0],other[0])<min(box[2],other[2]) and max(box[1],other[1])<min(box[3],other[3]):
                conflicts.update((i,j))
    for index,item in enumerate(replacements):
        validate_text(item['text'])
        box = boxes[index]
        background, foreground, ink_box, rows, columns = _layout(source,box)
        plan = {'box':box, 'background':background, 'inkBox':ink_box, 'text':item['text']}
        placed=[];text_box=box
        try:
            if index in conflicts:
                raise ImageEditError('수정할 이미지 영역이 겹칩니다. 하나씩 선택하거나 직접 영역 가림을 사용해 주세요.')
            if item['text'].strip():
                size,x,baseline=_typography(ink_box,item.get('originalText'))
                placed,text_box=_text_layout(item['text'],size,x,baseline)
                _check_space(source,box,text_box,background,occupied)
                plan.update(fontSize=size,textBox=text_box,foreground=foreground)
        except ImageEditError as error:
            if strict:raise
            plan['error']=str(error);plans.append(plan);continue
        x0,y0,x1,y1 = box
        # Always remove the entire original rectangle, even in partial mode.
        draw.rectangle((x0,y0,x1-1,y1-1),fill=background)
        for y,color in rows:
            draw.line((x0,y0+y,x1-1,y0+y),fill=color)
        for x,color in columns:
            draw.line((x0+x,y0,x0+x,y1-1),fill=color)
        if placed:
            tile_box=(min(x0,text_box[0]),min(y0,text_box[1]),max(x1,text_box[2]),max(y1,text_box[3]))
            tile=output.crop(tile_box);painter=ImageDraw.Draw(tile)
            for x,baseline,value,font in placed:
                painter.text((x-tile_box[0],baseline-tile_box[1]),value,font=font,fill=foreground,anchor='ls')
            output.paste(tile,tile_box[:2])
        occupied.append((min(x0,text_box[0]),min(y0,text_box[1]),max(x1,text_box[2]),max(y1,text_box[3])))
        plans.append(plan)
    # User-drawn opaque redactions take precedence over generated replacements.
    for region in regions:
        x0,y0,x1,y1 = pixel_box(region,source.size)
        draw.rectangle((x0,y0,x1-1,y1-1),fill='black')
    return output,plans


def save_image(source, destination, replacements, regions, *, strict=True):
    source = ImageOps.exif_transpose(source).convert('RGB')
    result,plans = render_image(source,replacements,regions,strict=strict)
    result.save(destination,format='PNG')
    with Image.open(destination) as reread:
        if reread.info or reread.size != result.size or ImageChops.difference(reread.convert('RGB'),result).getbbox():
            raise ImageEditError('수정 이미지의 픽셀·메타데이터 검증에 실패했습니다.')
    return plans
