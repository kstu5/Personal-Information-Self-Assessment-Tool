"""Local document notation and eligibility are not personal attributes.

No word is globally forbidden: explicit person/age fields retain precedence.
"""
import re

_DRAFT=re.compile(r'(?:계획|규정|공고|조례|정관|지침|일정|예산|보고서|방안)[ \t]*[（(](?P<word>안)[)）]')
_FAMILY=r'(?:조손|다자녀|한부모|다문화|기초생활|차상위|국가보훈)'
_CATEGORY=re.compile(rf'{_FAMILY}(?:[ \t]*[ㆍ·,/][ \t]*{_FAMILY})+|{_FAMILY}[ \t]*(?:가정|가구|자녀|지원대상)')
_LETTER='[가나다라마바사아자차카타파하]'
# Match source spans directly: normalizing punctuation first would invalidate
# the character positions used for document edits and image masks.
_MARKER=re.compile(rf'(?m)(?:^|(?<=[;；:：/／|]))[ \t]*{_LETTER}[.)．）]')
_PAREN_MARKER=re.compile(rf'(?<![가-힣A-Za-z0-9_])[（(][ \t]*{_LETTER}[ \t]*[)）]')
_ENUM_END=r'(?=$|[^가-힣A-Za-z0-9_]|(?:으로|로|은|는|을|를|과|와|의|도|만)(?=$|[ \t.,;:]))'
_ENUM=re.compile(rf'(?<![가-힣A-Za-z0-9_])(?:{_LETTER}[ \t]*[,，ㆍ·/／][ \t]*)+{_LETTER}'+_ENUM_END)
_SPACED_ENUM=re.compile(rf'(?<![가-힣A-Za-z0-9_]){_LETTER}(?:[ \t]+{_LETTER})+'+_ENUM_END)
_LIST_CUE=re.compile(r'항목|구분|목차|문항|선택지|선지|보기')
_GROUP=re.compile(r'(?<![가-힣])[가나다][ \t]*군(?=$|[^가-힣]|으로|에서|은|는|을|를|의|에|과|와|도|입니다)')
_ADMISSION=re.compile(r'모집|전형|정시|수능|군별|원서|입학|지원[ \t]*구분')
_ELIGIBILITY=re.compile(r'만학도|지원[ \t]*자격|모집[ \t]*대상|연령[ \t]*(?:기준|제한)|응시[ \t]*자격|입학[ \t]*전형')
_ACTUAL_AGE=re.compile(r'(?:실제|현재|본인)[ \t]*(?:나이|연령)|(?:나이|연령)[ \t]*(?:는|은|:|：)')


def filter_nonpersonal(text,detections):
    from backend.file_context import FileContext
    from backend.candidate_context import _person_field,birth_evidence
    fields=FileContext([{'id':'body','text':text,'target':{'kind':'text'}}]).fields['body']
    ranges=[m.span('word') for m in _DRAFT.finditer(text)]
    ranges.extend(m.span() for pattern in (_CATEGORY,_MARKER,_PAREN_MARKER,_ENUM) for m in pattern.finditer(text))
    for match in _SPACED_ENUM.finditer(text):
        lo=text.rfind('\n',0,match.start())+1;hi=text.find('\n',match.end())
        if _LIST_CUE.search(text[lo:len(text) if hi<0 else hi]):ranges.append(match.span())
    result=[]
    for d in detections:
        if d.label=='PERSON':
            protected=_person_field(text,d.start,d.end) or any(f.role=='person' and f.start<=d.start<d.end<=f.end for f in fields)
            if not protected:
                if any(a<=d.start<d.end<=b for a,b in ranges):continue
                lo=text.rfind('\n',0,d.start)+1;hi=text.find('\n',d.end)
                line=text[lo:len(text) if hi<0 else hi]
                if _ADMISSION.search(line) and any(m.start()<=d.start-lo<d.end-lo<=m.end() for m in _GROUP.finditer(line)):continue
        elif d.label in {'AGE','DT_BIRTH'}:
            lo=text.rfind('\n',0,d.start)+1;hi=text.find('\n',d.end)
            line=text[lo:len(text) if hi<0 else hi]
            tail=text[d.end:(len(text) if hi<0 else hi)]
            if _ELIGIBILITY.search(line) and not _ACTUAL_AGE.search(line):
                if d.label=='AGE' and re.match(r'[ \t]*(?:이상|이하|미만|초과)',tail):continue
                if d.label=='DT_BIRTH' and re.match(r'[ \t]*(?:현재[ \t]*)?기준',tail) and not birth_evidence(text,d.start,d.end):continue
        result.append(d)
    return result
