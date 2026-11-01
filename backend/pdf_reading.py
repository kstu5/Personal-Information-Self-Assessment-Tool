"""Native PDF text first; OCR only the remaining visible page regions.

All coordinates returned here refer to the original page preview pixels. The
erased OCR input is disposable and never replaces the preview or source PDF.
"""
import math
import unicodedata


def readable(char):
    return char.isspace() or char != '\ufffd' and unicodedata.category(char)[0] != 'C'


def area(rect):
    return max(0,rect[2]-rect[0])*max(0,rect[3]-rect[1])


def intersection(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))


def pixel_box(page,rect,size):
    import pymupdf as fitz
    transformed=fitz.Rect(rect)*page.rotation_matrix
    sx,sy=size[0]/page.rect.width,size[1]/page.rect.height
    return [max(0,min(size[0],transformed.x0*sx)),max(0,min(size[1],transformed.y0*sy)),
            max(0,min(size[0],transformed.x1*sx)),max(0,min(size[1],transformed.y1*sy))]


def regions(rectangles,size):
    """Merge overlapping crops; never truncate a page with many small images."""
    result=[]
    for rect in rectangles:
        if not rect or not all(math.isfinite(v) for v in rect):continue
        value=[max(0,math.floor(rect[0])-6),max(0,math.floor(rect[1])-6),
               min(size[0],math.ceil(rect[2])+6),min(size[1],math.ceil(rect[3])+6)]
        if not area(value):continue
        index=0
        while index<len(result):
            other=result[index]
            if value[0]<=other[2] and value[2]>=other[0] and value[1]<=other[3] and value[3]>=other[1]:
                value=[min(value[0],other[0]),min(value[1],other[1]),max(value[2],other[2]),max(value[3],other[3])]
                result.pop(index);index=0
            else:index+=1
        result.append(value)
        if len(result)>12:
            return [[0,0,*size]]
    return sorted(result,key=lambda b:(b[1],b[0]))


def page_reading_plan(page,size):
    """Separate native lines, trusted erasure boxes and areas needing OCR.

    Invisible OCR layers, broken character maps and text covered by later images
    are kept for inspection, but cannot suppress OCR of the visible content.
    """
    import pymupdf as fitz
    flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES
    raw=page.get_text('rawdict',flags=flags)
    log=page.get_bboxlog()
    trace={}
    for span in page.get_texttrace():
        opaque=span['type'] in {0,1} and span.get('opacity',0)>=.99 and not span.get('layer')
        covers=[rect for kind,rect,*_ in log[span['seqno']+1:]
                if kind in {'fill-image','fill-path'} and intersection(rect,span['bbox'])>0] if opaque else []
        for code,_,origin,bbox in span['chars']:
            visible=opaque and not any(intersection(bbox,cover)>area(bbox)*.1 for cover in covers)
            key=(round(origin[0],2),round(origin[1],2),code)
            # Multiple coincident layers are only trusted if all are visible.
            trace[key]=trace.get(key,True) and visible
    lines=[];trusted=[];requests=[];uncertain=False;broken=False
    for block_index,block in enumerate(raw['blocks']):
        for line_index,line in enumerate(block.get('lines',[])):
            text=[];boxes=[];line_trusted=[];bad=False;hidden=False
            for span in line['spans']:
                for glyph in span['chars']:
                    rect=pixel_box(page,glyph['bbox'],size)
                    origin=glyph['origin']
                    for char in glyph['c']:
                        text.append(char);boxes.append(rect)
                        if char.isspace():continue
                        good=readable(char)
                        visible=trace.get((round(origin[0],2),round(origin[1],2),ord(char)),False)
                        if good and visible and area(rect)>0:
                            line_trusted.append(rect)
                        else:
                            requests.append(rect);bad |= not good;hidden |= not visible
            if ''.join(text).strip():
                lines.append({'text':''.join(text),'boxes':boxes,'uncertain':bad or hidden,
                              'block':block_index,'line':line_index,'horizontal':tuple(line.get('dir',(1,0)))==(1,0)})
                uncertain |= hidden;broken |= bad
                if bad or hidden:
                    # Recover the whole word/line, not an isolated damaged digit
                    # with the rest of its name or identifier erased around it.
                    requests.append([min(b[0] for b in boxes),min(b[1] for b in boxes),
                                     max(b[2] for b in boxes),max(b[3] for b in boxes)])
                else:trusted.extend(line_trusted)
    if not lines:
        return {'lines':[],'trusted':[],'regions':[[0,0,*size]],'uncertain':False,'broken':False}
    for info in page.get_image_info():
        requests.append(pixel_box(page,info['bbox'],size))
    # Outlined letters may be vector shapes rather than text or raster images.
    # Ordinary table rules and simple rectangle backgrounds need no OCR.
    for drawing in page.get_cdrawings():
        items=drawing.get('items',[])
        if any(item[0]=='c' for item in items) or len(items)>4 or len(items)>1 and 'f' in drawing.get('type',''):
            requests.append(pixel_box(page,drawing['rect'],size))
    return {'lines':lines,'trusted':trusted,'regions':regions(requests,size),'uncertain':uncertain,'broken':broken}


def ocr_page_regions(image,plan,tessdata):
    """OCR a separate, masked input, retaining source-pixel offsets and boxes."""
    from PIL import ImageDraw
    from backend.image_ocr import read_image
    if not plan['regions']:return []
    working=image.copy()
    draw=ImageDraw.Draw(working)
    for rect in plan['trusted']:
        # PIL's right/bottom coordinates are inclusive. Padding covers the edge
        # antialiasing; the saved page asset itself remains completely untouched.
        draw.rectangle([max(0,math.floor(rect[0])-1),max(0,math.floor(rect[1])-1),
                        min(image.width-1,math.ceil(rect[2])),min(image.height-1,math.ceil(rect[3]))],fill='white')
    result=[]
    for x0,y0,x1,y1 in plan['regions']:
        for line in read_image(working.crop((x0,y0,x1,y1)),tessdata):
            translated={**line,'boxes':[[b[0]+x0,b[1]+y0,b[2]+x0,b[3]+y0] for b in line['boxes']]}
            if translated['text'].strip():result.append(translated)
    return result
