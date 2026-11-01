"""Source-bound assessment using existing NER outputs and explicit local evidence.

General DATE alone never vetoes a birthday. Supporting labels are ephemeral and
are never exposed as new PII types or persisted on the model between requests.
"""
from dataclasses import replace
from datetime import date
import re

_BIRTH_LABEL = r'(?:생년[ \t]*월일|생일|출생(?:연월일|일)?|DOB|date[ \t]+of[ \t]+birth|birth[ \t]*date)'
_BIRTH_BEFORE = re.compile(_BIRTH_LABEL + r'[ \t]*(?:은|는|이|가)?[ \t:：()\[\]-]*$', re.I)
_BIRTH_AFTER = re.compile(r'^[ \t]*(?:생(?=$|[\s,.;]|[가-힣]*입니다)|(?:에[ \t]*)?(?:태어(?:났|난|나)|출생(?:했|하)))')
_EVENT = (r'(?:배송|배달|발송|출고|작성|회의|면접|행사|교육|방문|예약|계약|구매|'
          r'발표|접수|제출|발급|입사|퇴사|졸업|수료|창립|설립|개최|마감)'
          r'(?:[ \t]*(?:예정|시작|종료|일정))?(?:일자|일시|일|날짜|기간)?')
_EVENT_BEFORE = re.compile(_EVENT + r'[ \t]*(?:은|는|이|가|을|를)?[ \t:：()\[\]-]*$')
_EVENT_AFTER = re.compile(r'^[ \t]*(?:에|부터)[ \t]*(?:'
                          r'(?:회의|면접|행사|교육)(?:에|를)?[ \t]*(?:참석|참가|개최|시작)|'
                          r'(?:설립|창립)(?:한|했|되)|(?:배송|배달|발송|출고)(?:이|가|을|를)?[ \t]*(?:시작|예정))')
_CALENDAR = re.compile(r'(?<!\d)(?:\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{4}년[ \t]*\d{1,2}월[ \t]*\d{1,2}일)(?!\d)')
_SENTENCE = re.compile(r'[!?;。]|(?<!\d)\.(?=\s|$)|(?<=\d)\.(?=\s+[가-힣A-Za-z])')
_PERSON_CUE = re.compile(r'(?:성명|이름|Name|담당자|작성자|신청인|지원자|수령인|참가자|대표자)[ \t:：은는]*$', re.I)
_HONORIFIC = re.compile(r'^[ \t]*(?:씨|님|선생님)(?=$|[\s,.]|[은는이가께])')
_ORDINARY_LIST = re.compile(r'(?:처리|운영)[ \t]*(?:방식|방법)[ \t]*(?:은|는|:|：)[ \t]*(?P<values>[^\n.!?;]+)')
_HUMAN = re.compile(r'성명|이름|담당자|작성자|신청인|지원자|수령인|참가자|대표자|(?:씨|님)(?=$|[\s,.])')
_NEGATION = re.compile(r'(?<![가-힣A-Za-z])(?P<word>안|못)[ \t]+'
    r'(?:되|된|됩|돼|됐|하|합|해|했|받|보내|보냈|읽|쓰|써|찾|열|적|넣|지우)'
    r'(?:니다|습니다|[가-힣]{0,3}(?:다|요|고|지|면|는|기|도))(?=$|[ \t.,!?])')


def review(state, reason, basis=None):
    return {'state': state, 'reason': reason, **({'basis':basis} if basis else {})}


def _local(text, start, end):
    """Never borrow prose from another paragraph/cell or across a date."""
    lo=text.rfind('\n',0,start)+1
    hi=text.find('\n',end)
    hi=len(text) if hi<0 else hi
    head=text[lo:start]; tail=text[end:hi]
    boundaries=list(_SENTENCE.finditer(head))
    if boundaries:head=head[boundaries[-1].end():]
    boundary=_SENTENCE.search(tail)
    if boundary:tail=tail[:boundary.start()]
    # An earlier/later date must not establish the current date's role.
    previous=list(_CALENDAR.finditer(head))
    if previous:head=head[previous[-1].end():]
    following=_CALENDAR.search(tail)
    if following:tail=tail[:following.start()]
    return head[-100:],tail[:80]


def birth_evidence(text,start,end):
    head,tail=_local(text,start,end)
    if text[start:end].endswith('년생') or _BIRTH_AFTER.match(tail):return True
    if _BIRTH_BEFORE.search(head):return True
    # Only a complete adjacent field label can cross a line boundary.
    if not head.strip():
        previous=text[:start].rstrip().rsplit('\n',1)[-1].strip(' \t:：')
        return bool(re.fullmatch(_BIRTH_LABEL,previous,re.I))
    return False


def _person_field(text,start,end):
    head,tail=_local(text,start,end)
    return bool(_PERSON_CUE.search(head) or _HONORIFIC.match(tail))


def _set(d,state,reason,basis=None):
    return replace(d,extra={**(d.extra or {}),'contextReview':review(state,reason,basis)})


def _date_covered(text,start,end,votes):
    """DATE/BIRTHDATE pieces may cover one date; never fill missing source text."""
    intervals=sorted((max(start,v.start),min(end,v.end)) for v in votes if start<v.end and v.start<end)
    pos=start
    for a,b in intervals:
        if a>pos and text[pos:a].strip():return False
        pos=max(pos,b)
    return not text[pos:end].strip()


def assess_candidates(text,detections,model_spans):
    if not model_spans:return detections
    # Validate supporting spans before they may suppress a real source target.
    for d in model_spans:
        if not 0<=d.start<d.end<=len(text) or text[d.start:d.end]!=d.text:
            raise ValueError('Invalid model context offsets')
    general=[d for d in model_spans if d.label=='GENERAL_DATE']
    births=[d for d in model_spans if d.label=='MODEL_BIRTHDATE']
    organizations=[d for d in model_spans if d.label=='ORGANIZATION']
    ordinary=[]
    for m in _ORDINARY_LIST.finditer(text):
        if ',' in m['values'] and not _HUMAN.search(m['values']):ordinary.append(m.span('values'))
    grammar=[m.span('word') for m in _NEGATION.finditer(text)]
    result=[]
    for d in detections:
        if d.label=='DT_BIRTH':
            head,tail=_local(text,d.start,d.end)
            birth=birth_evidence(text,d.start,d.end)
            event=bool(_EVENT_BEFORE.search(head) or _EVENT_AFTER.match(tail))
            vote=any(v.start<=d.start<d.end<=v.end for v in general)
            if vote and event and not birth:
                continue
            if birth:
                d=_set(d,'supported','출생 표현 또는 생년월일 항목과 연결된 날짜입니다.')
            else:
                d=_set(d,'uncertain','생년월일 근거가 충분하지 않습니다. 일정·기념일인지 원문을 확인하세요.')
        elif d.label=='PERSON':
            person=_person_field(text,d.start,d.end)
            excluded=any(a<=d.start<d.end<=b for a,b in ordinary+grammar)
            if excluded and not person:continue
            org=any(v.start<=d.start<d.end<=v.end for v in organizations)
            if org:
                d=_set(d,'uncertain','사람 항목과 기관명에 대한 모델 판단이 충돌합니다. 원문을 확인하세요.')
            elif len(d.text)==1 and re.fullmatch('[가-힣]',d.text) and not person:
                d=_set(d,'uncertain','한 글자 표현입니다. 이름·성씨인지 일반 표현인지 확인하세요.','short_name')
        result.append(d)
    # A model may call an explicitly labelled birthday a general DATE. Require
    # complete model date coverage and explicit birth prose, not BIRTHDATE alone.
    # Model fragments, invented digits and conflicting identifiers lose.
    from ko_pii.core.types import DetectionResult,RiskLevel
    for m in _CALENDAR.finditer(text):
        if not _date_covered(text,*m.span(),births+general):continue
        if not birth_evidence(text,*m.span()):continue
        try:
            year,month,day=map(int,re.findall(r'\d+',m[0]));value=date(year,month,day)
            if year<1900 or value>date.today():continue
        except ValueError:continue
        if any(d.start<m.end() and m.start()<d.end for d in result):continue
        result.append(DetectionResult('DT_BIRTH',m[0],m.start(),m.end(),RiskLevel.HIGH,.9,
            evidence=['context:model_and_birth_expression'],
            extra={'contextReview':review('supported','모델의 날짜 판단과 출생 표현을 함께 확인했습니다.')}))
    return result
