"""Real-model probes using identities and dates outside the shared document set."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CASES = [
    {'name': 'schedule_with_name', 'text': '회의 일시 2024년 8월 9일 담당자 윤지후',
     'require': [('PERSON', '윤지후')], 'forbid': [('DT_BIRTH', '2024년 8월 9일')]},
    {'name': 'birthday_and_issue_date', 'text': '성명 윤지후 생년월일 1991-02-06 작성일 2024년 8월 9일',
     'require': [('DT_BIRTH', '1991-02-06')], 'forbid': [('DT_BIRTH', '2024년 8월 9일')]},
    {'name': 'signature', 'text': '2024년 8월 9일 신청인 윤지후',
     'require': [('PERSON', '윤지후')], 'forbid': [('DT_BIRTH', '2024년 8월 9일')]},
    {'name': 'birth_before_signature', 'text': '생년월일: 1991년 2월 6일 지원자 윤지후',
     'require': [('DT_BIRTH', '1991년 2월 6일')], 'forbid': []},
    {'name': 'separate_field_labels', 'text': '작성일\n\n2024.08.09\n\n생년월일\n\n1991.02.06',
     'require': [('DT_BIRTH', '1991.02.06')], 'forbid': [('DT_BIRTH', '2024.08.09')]},
    {'name': 'born_marker', 'text': '작성일 확인 후 1991년생 윤지후',
     'require': [('DT_BIRTH', '1991년생')], 'forbid': []},
    {'name': 'no_old_date_context_leak', 'text': '작성일: 2024.08.09\n\n성명 윤지후\n\n1991년 2월 6일',
     'require': [('DT_BIRTH', '1991년 2월 6일')], 'forbid': [('DT_BIRTH', '2024.08.09')]},
    {'name': 'new_road_address', 'text': '주소: 울산광역시 남구 새연구로 7-3, 105동 204호\n전화 010-0000-1111',
     'require': [('ADDRESS', '울산광역시 남구 새연구로 7-3, 105동 204호'), ('PHONE', '010-0000-1111')], 'forbid': []},
    {'name': 'new_venue_address', 'text': '장소: 대구광역시 수성구 새연구길 8, 3층\n문의 윤지후',
     'require': [('ADDRESS', '대구광역시 수성구 새연구길 8, 3층')], 'forbid': []},
    {'name': 'ordinary_words', 'text': '검토용_자료\n업무 역량 Python',
     'require': [], 'forbid': [('PERSON', '검토용'), ('PERSON', 'th'), ('PERSON', 'Python')]},
]

def main():
    from backend.model_a import ModelA, DELEGATED_LABELS
    from backend.detection_context import refine_detections
    from ko_pii import detect_all
    from ko_pii.integrations.hybrid import MergeMode, merge_detections
    model = ModelA()
    results = []
    for case in CASES:
        text = case['text']
        before = merge_detections(detect_all(text), model.detect(text), mode=MergeMode.ROLE_SPLIT, role_split_labels=DELEGATED_LABELS)
        after = refine_detections(text, before)
        def evaluate(items):
            values = {(d.label, d.text) for d in items}
            return {'missing': [pair for pair in case['require'] if pair not in values],
                    'unwanted': [pair for pair in case['forbid'] if pair in values]}
        for items in (before, after):
            assert all(text[d.start:d.end] == d.text for d in items)
            assert all(a.end <= b.start for a, b in zip(items, items[1:]))
        row = {**case, 'before': evaluate(before), 'after': evaluate(after),
               'detections': [{'text': d.text, 'label': d.label} for d in after]}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    folder = ROOT / 'local-only/context-review'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'probes.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    assert all(not r['after']['missing'] and not r['after']['unwanted'] for r in results), 'See local-only/context-review/probes.json'

if __name__ == '__main__':
    main()
