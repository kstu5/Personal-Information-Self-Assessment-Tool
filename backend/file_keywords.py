"""Literal original-text matches with server-derived UTF-16 positions."""
from backend.documents import DocumentError


def keyword_matches(parts, candidates, query):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise DocumentError('검색어는 공백만 제외하고 1~2,000자로 입력해 주세요.')
    if any(0xd800 <= ord(c) <= 0xdfff for c in query):
        raise DocumentError('검색어의 문자 형식이 올바르지 않습니다.')
    known = {}
    for candidate in candidates:
        known.setdefault(candidate['part'], []).append(candidate)
    result = []
    for part in parts:
        text = part['text']
        pos = 0
        while (lo := text.find(query, pos)) >= 0:
            hi = lo + len(query)
            start = len(text[:lo].encode('utf-16-le')) // 2
            end = start + len(query.encode('utf-16-le')) // 2
            overlaps = [c for c in known.get(part['id'], []) if start < c['end'] and c['start'] < end]
            reason = '이미 검토 후보가 있는 범위입니다. 해당 후보에서 범위를 변경하세요.' if overlaps else ''
            # OCR positions must actually be usable for masking, not just for display.
            if part.get('asset') and not any(b[2] > b[0] and b[3] > b[1] for b in part.get('boxes', [])[lo:hi]):
                reason = '이미지 글자 위치를 확인할 수 없습니다. 이미지에서 영역을 직접 지정하세요.'
            result.append({'id': f"{part['id']}:{start}:{end}", 'part': part['id'],
                           'start': start, 'end': end, 'text': query, 'location': part['location'],
                           'before': text[max(0, lo-50):lo], 'after': text[hi:hi+50],
                           'reason': reason, 'readingMethod': part.get('readingMethod', 'ocr' if part.get('asset') else 'native')})
            if len(result) > 6000:
                raise DocumentError('검색 결과가 6천 곳을 넘습니다. 검색어를 더 구체적으로 입력해 주세요.')
            pos = hi  # Non-overlapping literal occurrences, preserving original offsets.
    return result
