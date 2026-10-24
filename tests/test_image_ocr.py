from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.runtime/file-python'))
from backend.file_review import image_mask_boxes


def test_full_image_mask_covers_whole_name_and_partial_keeps_first_character():
    c={'text':'김민수','label':'PERSON','boxes':[[10,20,31,50],[34,19,53,51],[56,21,79,49]]}
    asset={'width':100,'height':80}
    full=image_mask_boxes(c,'full',asset);partial=image_mask_boxes(c,'partial',asset)
    assert len(full)==len(partial)==1
    assert full[0][0]<=10 and full[0][2]>=79 and full[0][1]<=19 and full[0][3]>=51
    assert partial[0][0]>31 and partial[0][2]>=79
    assert image_mask_boxes({'text':'김','label':'PERSON','boxes':[[0,0,2,2]]},'full',{'width':2,'height':2})==[[0,0,2,2]]


def test_large_dark_korean_title_and_small_name_are_both_read(tmp_path,monkeypatch):
    from PIL import Image,ImageDraw,ImageFont
    from backend.image_ocr import read_image
    font=Path('C:/Windows/Fonts/malgunbd.ttf')
    if not font.exists():pytest.skip('Korean fixture font not installed')
    monkeypatch.chdir(ROOT/'.runtime/file-tools')
    im=Image.new('RGB',(1600,900),(12,21,43));draw=ImageDraw.Draw(im)
    draw.text((100,220),'사물인터넷과 보안',font=ImageFont.truetype(str(font),106),fill='white')
    draw.text((100,620),'담당자 김민수',font=ImageFont.truetype(str(font),32),fill='white')
    lines=read_image(im,'tessdata');text='\n'.join(p['text'] for p in lines)
    assert '보안' in text and '보우' not in text and '김민수' in text,text
    line=next(p for p in lines if '보안' in p['text']);index=line['text'].index('보안')
    boxes=line['boxes'][index:index+2]
    assert len(boxes)==2 and boxes[0][0]<boxes[1][0] and all(b[2]-b[0]>50 and b[3]-b[1]>50 for b in boxes)
    assert all(len(p['text'])==len(p['boxes'])==len(p['confidences']) for p in lines)
