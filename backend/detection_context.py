"""Bounded context checks around existing model/rule spans.

No document identity or synthetic value is special-cased. Refinements keep exact
source offsets, preserve ambiguous birth dates, and never join document fields.
"""
from __future__ import annotations

from dataclasses import replace
import re

_BIRTH = re.compile(r'생년월일|생일|출생(?:연월일|일)?|태어난|DOB|date\s+of\s+birth|birth\s*date', re.I)
_OTHER_DATE = re.compile(r'(?:작성|발표|배포|발송|배송|접수|등록|신청|회의|행사|면접|제출|발급|결재|시행|계약|입사|퇴사|졸업|수료|교육|개최|신청마감|마감)[ \t]*(?:예정[ \t]*)?(?:일시|일자|일|날짜|기간)|(?:회의|행사|면접|교육|개최)[ \t]*일시|(?:일시|작성일|발송예정일|기준일)')
_SIGNATURE = re.compile(r'^[ \t]*(?:지원자|작성자|작성인|신청인|서명)(?=[ \t:：]|$)')
_ADDRESS_UNIT = r'(?:동|호|층)(?![가-힣A-Za-z0-9])'
_ADDRESS_TAIL = re.compile(rf'(?:{_ADDRESS_UNIT})?(?:[ \t]*,?[ \t]*\d+(?:-\d+)?[ \t]*{_ADDRESS_UNIT}){{0,4}}')
_PURPOSE = re.compile(r'(?<![가-힣])(?:공유|배포|인쇄|발표|검토|보관|업무|내부|외부)용(?=[_ \t-]+(?:명단|목록|자료|현황|양식|대장|내역|기록))')
_TECH_LABEL = re.compile(r'업무[ \t]*역량|기술[ \t]*스택|개발[ \t]*언어|프로그래밍[ \t]*언어|사용[ \t]*(?:언어|도구)')
_PERSON_LABEL = re.compile(r'성명|이름|담당자|지원자|작성자')
_TECH_TERMS = frozenset({'python', 'javascript', 'typescript', 'java', 'sql', 'excel', 'powerpoint', 'word', 'html', 'css'})
_ANCHORED_ADDRESS = re.compile(
    r'(?<![가-힣])(?:거주[ \t]*주소|배송[ \t]*주소|수령[ \t]*주소|주소|거주지|배송지|소재지|장소)'
    r'[ \t\n:：]{0,8}'
    r'(?P<address>[가-힣]{2,}(?:특별자치도|특별자치시|특별시|광역시|도|시)[ \t]+'
    r'(?:[가-힣0-9·]+(?:시|군|구)[ \t]+){0,2}'
    r'[가-힣0-9·]+(?:대로|로|길)[ \t]+\d+(?:-\d+)?'
    r'(?:[ \t]*,?[ \t]*\d+(?:-\d+)?[ \t]*(?:동|호|층)){0,4}'
    r')(?![가-힣A-Za-z0-9-])')


def _last(pattern, text):
    return max((m.start() for m in pattern.finditer(text)), default=-1)


def _ordinary_date(text, start, end):
    # "...일생" is an explicit birthday marker even in otherwise mixed prose.
    if text[end:end + 1] == '생' or text[start:end].endswith('년생'):
        return False
    before = text[max(0, start - 120):start]
    head = before.rsplit('\n', 1)[-1]
    if not head.strip():
        previous = before.rstrip().rsplit('\n', 1)[-1].strip(' \t:：')
        # A table label may be a separate field. Inherit only a short, explicit
        # label, never a preceding value, name, sentence, or old date.
        if len(previous) <= 20 and (_BIRTH.fullmatch(previous) or _OTHER_DATE.fullmatch(previous)):
            head = previous
    birth, other = _last(_BIRTH, head), _last(_OTHER_DATE, head)
    if other > birth:
        hint = list(_OTHER_DATE.finditer(head))[-1]
        if re.fullmatch(r'[ \t:：은는이자()\[\]-]{0,12}', head[hint.end():]):
            return True
    # Signature dates followed by an applicant name caused the upstream generic
    # name-near-date heuristic to emit a birthday. Explicit DOB context wins.
    return birth < 0 and bool(_SIGNATURE.match(text[end:end + 50]))


def refine_detections(text, detections):
    from ko_pii.core.overlap import resolve_overlaps
    detections = list(detections)
    for match in _ANCHORED_ADDRESS.finditer(text):
        start, end = match.span('address')
        fragments = [d for d in detections if d.label == 'ADDRESS' and start <= d.start < d.end <= end]
        if not fragments or any(d.label != 'ADDRESS' and start < d.end and d.start < end for d in detections):
            continue
        # The model must already have found address fragments. Join only a
        # labelled, syntactically complete Korean road address, within one line.
        detections = [d for d in detections if not any(d is fragment for fragment in fragments)]
        detections.append(replace(fragments[0], start=start, end=end, text=text[start:end],
                                  evidence=[*fragments[0].evidence, 'context:labelled_road_address']))
    result = []
    purposes = [(m.start(), m.end()) for m in _PURPOSE.finditer(text)]
    for detection in detections:
        if detection.label == 'DT_BIRTH' and _ordinary_date(text, detection.start, detection.end):
            continue
        if detection.label == 'PERSON':
            # A NAME tag on the middle of an English word is not a complete
            # name token. Isolated short names such as Li remain eligible.
            latin = bool(re.fullmatch(r'[A-Za-z]+', detection.text))
            adjacent = text[max(0, detection.start - 1):detection.start] + text[detection.end:detection.end + 1]
            if latin and any(c.isascii() and c.isalpha() for c in adjacent):
                continue
            if any(a <= detection.start and detection.end <= b for a, b in purposes):
                continue
            head = text[max(0, detection.start - 80):detection.start].rsplit('\n', 1)[-1]
            if detection.text.lower() in _TECH_TERMS and _last(_TECH_LABEL, head) > _last(_PERSON_LABEL, head):
                continue
        if detection.label == 'ADDRESS' and detection.text[-1:].isdigit():
            match = _ADDRESS_TAIL.match(text, detection.end)
            if match and match.end() > detection.end and not any(
                other is not detection and detection.end <= other.start < match.end() for other in detections):
                detection = replace(detection, end=match.end(), text=text[detection.start:match.end()],
                                    evidence=[*detection.evidence, 'context:address_detail_suffix'])
        result.append(detection)
    # An extended address may meet another candidate. Keep the same upstream
    # risk-first overlap policy, so phone/ID candidates cannot be swallowed.
    return resolve_overlaps(result)
