"""Deterministic file-local proposals; never changes detection or source data."""
from datetime import date
import re
import unicodedata

REVIEW_LABELS = {'DOC_ID', 'COURT_CASE', 'PETITION_ID', 'BUSINESS_REG', 'CORP_REG', 'EDI_DRUG', 'URL'}
ALIASES = {'VEHICLE': '차량', 'EMPLOYEE_ID': '사번', 'MEDICAL_INSURANCE': '보험번호', 'PRESCRIPTION_ID': '처방번호'}


def _letters(number):
    value = ''
    while number:
        number, digit = divmod(number - 1, 26)
        value = chr(65 + digit) + value
    return value


def _birth_year(text):
    value = unicodedata.normalize('NFKC', text).strip()
    match = re.fullmatch(r'((?:19|20)\d{2})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})일?', value)
    if not match:
        match = re.fullmatch(r'((?:19|20)\d{2})(\d{2})(\d{2})', value)
    if match:
        try:
            return str(date(*map(int, match.groups())).year) + '년'
        except ValueError:
            pass
    return None


def _area(text):
    tokens, kept = text.strip().split(), []
    for token in tokens[:3]:
        if not re.fullmatch(r'[가-힣]{1,20}(?:특별자치도|특별자치시|특별시|광역시|도|시|군|구)', token):
            break
        kept.append(token)
    return ' '.join(kept) + ' ***' if kept and len(kept) < len(tokens) else None


def proposals(candidates, aliases=None, *, scope='file'):
    """Aliases are scoped to this file and identify equal values, not people."""
    aliases = {} if aliases is None else aliases
    counts, result = {}, {}
    for label, _ in aliases:
        counts[label] = counts.get(label, 0) + 1
    for candidate in candidates:
        label, text = candidate['label'], candidate['text']
        choice, rule = {'mode': 'full'}, '전체 가림'
        if candidate.get('editable') is False:
            choice,rule=None,candidate.get('readOnlyReason','이 글자 구간은 수정 저장을 지원하지 않습니다.')
        elif label in REVIEW_LABELS:
            choice, rule = None, '개인·사건 연결 여부 확인 후 직접 지정'
        elif label in {'PERSON', 'PHONE', 'FAX', 'EMAIL', 'RRN', 'FRN', 'CARD', 'ACCOUNT'}:
            choice = {'mode': 'partial'}
            rule = {'PERSON': '첫 글자만 유지', 'PHONE': '앞자리·끝 4자리 유지',
                    'FAX': '앞자리·끝 4자리 유지', 'EMAIL': '계정 첫 글자·도메인 유지',
                    'RRN': '앞 6자리 유지', 'FRN': '앞 6자리 유지',
                    'CARD': '끝 4자리만 유지', 'ACCOUNT': '끝 4자리만 유지'}[label]
            digits = re.sub(r'\D', '', text, flags=re.ASCII)
            valid = (label == 'PERSON' or label == 'EMAIL' and re.fullmatch(r'[^\s@]+@[^\s@]+', text)
                     or label in {'PHONE', 'FAX'} and len(digits) >= 8
                     or label in {'RRN', 'FRN'} and len(digits) == 13
                     or label in {'CARD', 'ACCOUNT'} and len(digits) > 4)
            if not valid or label != 'PERSON' and any(c.isdecimal() and not c.isascii() for c in text):
                choice, rule = {'mode': 'full'}, '형식이 불확실하여 전체 가림'
        elif label == 'ADDRESS':
            area = _area(text)
            if area:
                choice, rule = {'mode': 'custom', 'text': area}, '시·군·구까지만 유지'
            else:
                rule = '행정구역 경계가 불확실하여 전체 가림'
        elif label == 'DT_BIRTH':
            year = _birth_year(text)
            if year:
                choice, rule = {'mode': 'custom', 'text': year}, '출생연도만 유지'
            else:
                rule = '생년월일 형식이 불확실하여 전체 가림'
        elif label == 'AGE':
            age = re.fullmatch(r'(?:만\s*)?(\d{1,3})\s*세?', unicodedata.normalize('NFKC', text).strip())
            if age and 0 <= int(age[1]) <= 120:
                number = int(age[1])
                choice = {'mode': 'custom', 'text': '10세 미만' if number < 10 else f'{number // 10 * 10}대'}
                rule = '10세 단위 연령대로 변경'
            else:
                rule = '나이 범위가 불확실하여 전체 가림'
        elif label in ALIASES:
            key = (label, text)
            if key not in aliases:
                counts[label] = counts.get(label, 0) + 1
                aliases[key] = f'{ALIASES[label]} {_letters(counts[label])}'
            choice, rule = {'mode': 'custom', 'text': aliases[key]}, f'현재 {"게시글" if scope=="post" else "파일"}의 같은 값에 같은 대체 표시'
        elif label in {'DRIVER_LICENSE', 'PASSPORT'}:
            rule = '식별번호 전체 가림'
        elif label in {'API_KEY', 'PASSWORD'}:
            rule = '인증정보 전체 가림'
        elif label == 'USER_DEFINED':
            rule = '사용자가 추가한 범위 전체 가림'
        elif label in {'NATIONALITY', 'EDUCATION', 'MAJOR', 'POSITION', 'HEIGHT', 'WEIGHT'}:
            rule = '개인 속성 전체 가림 · 필요하면 개별 변경'
        if choice and choice['mode'] == 'custom' and candidate.get('asset') and not candidate.get('imageTextEditable'):
            choice, rule = {'mode': 'full'}, 'PDF·내장 이미지는 문구 교체 대신 전체 영역 가림'
        result[candidate['id']] = {'choice': choice, 'rule': rule}
    return result
