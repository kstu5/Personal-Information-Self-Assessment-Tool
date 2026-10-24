"""Run three pre-annotated synthetic posts through the production local API."""
from pathlib import Path
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.runtime' / 'python'), str(ROOT)]


def span_for(case, spec):
    text = case[spec['source']]
    position = -1
    for _ in range(spec.get('occurrence', 1)):
        position = text.index(spec['text'], position + 1)
    start = len(text[:position].encode('utf-16-le')) // 2
    end = start + len(spec['text'].encode('utf-16-le')) // 2
    return {**spec, 'start': start, 'end': end}


def main():
    from fastapi.testclient import TestClient
    from backend.app import create_app
    from backend.documents import serialize_document, parse_document

    fixture = ROOT / 'research' / 'community_cases_v1.json'
    data = json.loads(fixture.read_text(encoding='utf-8'))
    out = ROOT / 'output' / 'community-review'
    out.mkdir(parents=True, exist_ok=True)
    app = create_app(8765)
    report = {
        'testedAt': datetime.now(timezone.utc).isoformat(),
        'fixtureSha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
        'scope': data['scope'], 'annotationPolicy': data['annotationPolicy'],
        'execution': 'FastAPI TestClient calls unchanged POST /api/check and the production multiprocessing Detector. No mocked detection.',
        'cases': [],
    }
    with TestClient(app, base_url='http://127.0.0.1:8765', headers={'Origin': app.state.origin, 'X-App-Token': app.state.token}) as client:
        for revision, case in enumerate(data['cases'], 1):
            expected = [span_for(case, e) for e in case['expected']]
            response = client.post('/api/check', json={'title': case['title'], 'body': case['body'], 'revision': revision})
            response.raise_for_status()
            result = response.json()
            assert result['revision'] == revision
            found = result['candidates']
            for c in found:
                raw = case[c['source']].encode('utf-16-le')
                assert raw[c['start']*2:c['end']*2].decode('utf-16-le') == c['text']
            used = set()
            outcomes = []
            for n, item in enumerate(expected, 1):
                overlap = [c for c in found if c['source'] == item['source'] and c['start'] < item['end'] and item['start'] < c['end']]
                exact = [c for c in overlap if c['label'] == item['label'] and (c['start'], c['end']) == (item['start'], item['end'])]
                same_label = [c for c in overlap if c['label'] == item['label']]
                if exact:
                    status = 'exact'
                elif same_label:
                    status = 'partial'
                elif overlap:
                    status = 'wrong_label'
                else:
                    status = 'missed'
                used.update(c['id'] for c in overlap)
                outcomes.append({**item, 'itemId': f'{case["id"]}-E{n:02}', 'status': status, 'actual': overlap})
            extras = [c for c in found if c['id'] not in used]
            status_count = Counter(o['status'] for o in outcomes)
            negatives = []
            for e in case['negativeExamples']:
                s = span_for(case, e)
                negatives.append({**s, 'actual': [c for c in found if c['source'] == s['source'] and c['start'] < s['end'] and s['start'] < c['end']]})
            filename = f'{case["id"]}_{case["genre"].replace(" ", "_")}.piipost'
            content = serialize_document(case['title'], case['body'])
            (out / filename).write_bytes(content)
            reopened = parse_document((out / filename).read_bytes())
            assert (reopened['title'], reopened['body']) == (case['title'], case['body'])
            counts = {k: status_count[k] for k in ['exact', 'partial', 'wrong_label', 'missed']}
            counts.update(expected=len(expected), candidates=len(found), extra=len(extras))
            record = {**case, 'expected': outcomes, 'negativeExamples': negatives,
                      'actual': found, 'extras': extras, 'counts': counts,
                      'byRisk': dict(Counter(c['risk'] for c in found)), 'engine': result['engine'],
                      'elapsedMs': result['elapsedMs'], 'inputFile': filename,
                      'checks': {'allReturnedSpansMatchOriginal': True, 'fileRoundTrip': True}}
            report['cases'].append(record)
            print(json.dumps({'id': case['id'], 'counts': counts, 'outcomes': [(e['text'], e['status'], [(c['text'], c['label']) for c in e['actual']]) for e in outcomes], 'extras': [(c['source'], c['text'], c['label'], c['risk']) for c in extras]}, ensure_ascii=False))
    report['totals'] = {k: sum(c['counts'][k] for c in report['cases']) for k in ['expected', 'candidates', 'exact', 'partial', 'wrong_label', 'missed', 'extra']}
    (out / 'community-evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'totals': report['totals']}, ensure_ascii=False))


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
