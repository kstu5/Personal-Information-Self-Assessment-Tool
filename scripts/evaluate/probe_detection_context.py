"""Isolate input differences without changing the installed detector or application."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.runtime' / 'python'), str(ROOT)]
from scripts.evaluate.rule_baseline import detect_document

PAIRS = [
    ('주소 쉼표', '주소: 서울특별시 마포구 예시로 12, 302호', '주소: 서울특별시 마포구 예시로 12 302호'),
    ('건물명 앞 쉼표', '주소: 경기도 수원시 영통구 예시로 45, 가상아파트 101동 1203호', '주소: 경기도 수원시 영통구 예시로 45 가상아파트 101동 1203호'),
    ('이름의 어미', '김하늘입니다.', '김하늘에게 연락해 주세요.'),
    ('계좌 키워드', '배송비 3500원은 110-000-000000으로 보내 주세요.', '계좌번호: 110-000-000000'),
    ('물건과 사람', '선반의 높이는 180cm이고 무게는 70kg입니다.', '제 키는 180cm이고 몸무게는 70kg입니다.'),
    ('한글 숫자', '연락처: 공일공-공공공공-공공공공', '연락처: 010-0000-0000'),
]

records=[]
for name, before, after in PAIRS:
    row={'topic':name,'a':{'input':before, **detect_document('',before)},'b':{'input':after, **detect_document('',after)}}
    records.append(row)
    print(json.dumps({'topic':name,'a':[(c['text'],c['label']) for c in row['a']['candidates']], 'b':[(c['text'],c['label']) for c in row['b']['candidates']]},ensure_ascii=False))

source=json.loads((ROOT/'research'/'community_cases_v1.json').read_text(encoding='utf-8'))
full=[]
for c in source['cases'][:2]:
    original=c['body']
    variant=original.replace('12, 302호','12 302호').replace('45, 가상아파트','45 가상아파트')
    full.append({'case':c['id'],'change':'Remove the comma immediately preceding the address detail; original fixture unchanged.',
                 'originalAddresses':[x for x in detect_document(c['title'],original)['candidates'] if x['label']=='ADDRESS'],
                 'variantAddresses':[x for x in detect_document(c['title'],variant)['candidates'] if x['label']=='ADDRESS']})
    print(json.dumps(full[-1],ensure_ascii=False))

report={'date':'2026-10-16','engine':'ko-pii 1.16.0','scope':'Synthetic paired-input diagnostics only. No application or detector changes. Shorter variants can change context and are not a general accuracy evaluation. Removing a comma changes offsets; a production fix must preserve the original text and offsets.', 'pairs':records,'fullPostAddressVariants':full}
from ko_pii import detect_all
report['confidenceDiagnostics'] = [
    {'case': c['id'], 'items': [
        {'text': d.text, 'label': d.label, 'confidence': d.confidence,
         'risk': d.risk_level.name, 'evidence': d.evidence, 'start': d.start, 'end': d.end}
        for d in detect_all(c['body']) if d.label in {'PERSON', 'HEIGHT', 'WEIGHT'}
    ]} for c in source['cases']
]
(ROOT/'research'/'detection_context_probes_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
