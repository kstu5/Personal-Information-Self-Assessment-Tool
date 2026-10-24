"""Small, explicitly synthetic exact-span evaluation, not a production benchmark."""
from pathlib import Path
import json
import sys
import time
from collections import Counter

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.runtime'/'python'));sys.path.insert(0,str(ROOT))
from scripts.evaluate.rule_baseline import detect_document

CASES=[
    ('mobile','연락처: 010-0000-0000',[('PHONE','010-0000-0000')]),
    ('email','문의: member@example.com',[('EMAIL','member@example.com')]),
    ('identifier','주민등록번호: 990101-1000000',[('RRN','990101-1000000')]),
    ('name-with-particle','김하늘에게 연락해 주세요.',[('PERSON','김하늘')]),
    ('name-with-ending','김하늘입니다.',[('PERSON','김하늘')]),
    ('full-address','주소: 서울특별시 마포구 예시로 12, 302호',[('ADDRESS','서울특별시 마포구 예시로 12, 302호')]),
    ('non-person','오늘은 김치와 박하차를 먹고 책을 읽었습니다.',[]),
    ('account-context','계좌번호: 110-123-456789',[('ACCOUNT','110-123-456789')]),
    ('account-no-context','110-123-456789',[('ACCOUNT','110-123-456789')]),
    ('repeat-emoji','😀 전화: 010-0000-0000 / 반복: 010-0000-0000',[('PHONE','010-0000-0000'),('PHONE','010-0000-0000')]),
    ('fullwidth','전화: ０１０-００００-００００',[('PHONE','０１０-００００-００００')]),
    ('no-candidates','안녕하세요.',[]),
]


def main():
    records=[]; metrics={}
    for name,text,labels in CASES:
        expected=[];search_from={}
        for label,value in labels:
            start=text.index(value,search_from.get(value,0));search_from[value]=start+len(value)
            expected.append((label,len(text[:start].encode('utf-16-le'))//2,len(text[:start+len(value)].encode('utf-16-le'))//2))
        found=detect_document('',text)['candidates']
        actual=[(c['label'],c['start'],c['end']) for c in found]
        exp,act=Counter(expected),Counter(actual)
        correct=exp & act
        for label in {x[0] for x in exp}|{x[0] for x in act}:
            m=metrics.setdefault(label,{'tp':0,'fp':0,'fn':0})
            m['tp']+=sum(n for x,n in correct.items() if x[0]==label)
            m['fp']+=sum(n for x,n in (act-correct).items() if x[0]==label)
            m['fn']+=sum(n for x,n in (exp-correct).items() if x[0]==label)
        records.append({'case':name,'input':text,'expected':expected,'actual':actual,'exactMatch':exp==act})
    for m in metrics.values():
        m['precision']=round(m['tp']/(m['tp']+m['fp']),3) if m['tp']+m['fp'] else None
        m['recall']=round(m['tp']/(m['tp']+m['fn']),3) if m['tp']+m['fn'] else None
    text='연락처: 010-0000-0000\n'*1000
    start=time.perf_counter();large=detect_document('',text);elapsed=time.perf_counter()-start
    report={'scope':'12 synthetic fixtures. Exact label and UTF-16 span matching. Not a representative accuracy estimate. Full address includes the room number by application annotation policy.',
            'engine':'ko-pii 1.16.0','cases':records,'byLabel':metrics,
            'loadCheck':{'characters':len(text),'candidates':len(large['candidates']),'seconds':round(elapsed,3)}}
    out=ROOT/'docs'/'verification'/'detection-evaluation.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'caseCount':len(records),'exactMatches':sum(x['exactMatch'] for x in records),'byLabel':metrics,'loadCheck':report['loadCheck']},ensure_ascii=False))


if __name__=='__main__':main()
