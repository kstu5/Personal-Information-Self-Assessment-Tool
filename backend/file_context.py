"""Ephemeral field evidence for one file scan; no shared vocabulary or training.

Labels establish local roles and validate identifier fields, while repeated
organization phrases require unambiguous full-phrase evidence. Original text and
edit targets are never changed to provide context to the model.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from backend.identifier_rules import FIELD_LABELS, NUMERIC_LABELS, field_detection
from backend.credentials import CREDENTIAL_FIELD_LABELS, CREDENTIAL_LABELS, password_field_role

_ROLES = {
    'person': ('성명', '이름', 'Name', '담당자', '연락 담당자', '신청인', '지원자',
               '참가자', '수령인', '작성자', '직원명', '대표자', '추천인', '교육 담당자'),
    'organization': ('회사명', '기업명', '법인명', '기관명', '소속 기관', '협력 기관',
                     '운영 기관', '교육 기관', '담당 기관', '회사', '기관',
                     'Company', 'Employer', 'Organization'),
    'ordinary': ('사업명', '행사명', '교육명', '자료 제목', '문서 제목', '업무', '담당 업무',
                 '전형명', '전형 유형', '모집군', '모집 구분', '지원 자격', '지원 대상', '연령 기준',
                 '처리 방법', '운영 방식', '사업 구호', '배포 범위', '부서명', '시스템명',
                 '물품', '준비 물품', '업무 역량', '기술 스택', '개발 언어',
                 '프로그래밍 언어', '사용 언어', '사용 도구'),
    # These labels delimit other fields, but never suppress their values.
    'other': ('비고', '메모', '설명', '내용', '주소', '연락처', '전화번호', '휴대전화',
              '휴대폰', '핸드폰', '이전 연락처', '이메일', '생년월일', '배송 예정일',
              '작성일', '회의일', '날짜', '항목', '자료 구분', '구분', '연번', '순번'),
    'object': ('물품 규격', '상품 규격', '제품 크기', '배송 물품 무게', '물품 무게', '장비 수량'),
}
_ROLES.update(CREDENTIAL_FIELD_LABELS)
for _code, _labels in FIELD_LABELS.items():
    _ROLES['type:' + _code] = _labels
_normalize = lambda value: re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).casefold()
_ROLE_BY_LABEL = {_normalize(label): role for role, names in _ROLES.items() for label in names}


def _label_pattern(label):
    chars=[]
    for c in re.sub(r'\s+', '', label):
        if c.isascii() and c.isalnum():chars.append('['+c+chr(ord(c)+0xfee0)+']')
        else:chars.append(re.escape(c))
    return r'[ \t]*'.join(chars)


_LABEL_PATTERN = '|'.join(_label_pattern(label)
                         for label in sorted((label for names in _ROLES.values() for label in names), key=len, reverse=True))
_INLINE = re.compile(r'(?<![가-힣A-Za-z0-9_Ａ-Ｚａ-ｚ０-９])(?P<label>' + _LABEL_PATTERN + r')[ \t]*[:：][ \t]*', re.I)
_PLAIN = re.compile(r'^[ \t]*(?P<label>' + _LABEL_PATTERN + r')[ \t]+(?P<value>\S.*)$', re.I)
_HUMAN_CUE = re.compile(r'담당자|대표자?|작성자|신청인|지원자|수령인|참가자|직원|성명|이름|'
                        r'[가-힣]{2,5}[ \t]*(?:씨|님)(?=$|[\s,.;])|[와과][ \t]*(?:협의|통화|면담|상담|연락)')
_ORG_SUFFIX = re.compile(r'(?:주식회사|유한회사|은행|뱅크|도서관|센터|연구소|연구원|재단|협회|'
                         r'협동조합|교육원|진흥원|복지관|학습관|대학교|병원|공사|공단|Inc\.?|Ltd\.?|Bank)$', re.I)
_PLACEHOLDERS = frozenset({'미정', '없음', '해당없음', '비공개', '공개하지않음', '확인중',
                           '미입력', '삭제', '담당자', '개인정보', '테스트', '성명', '이름', 'name', 'na', 'none'})


@dataclass(frozen=True)
class Field:
    start: int
    end: int
    role: str


def field_role(text):
    return _ROLE_BY_LABEL.get(_normalize(text.strip(' \t\r\n:：'))) or password_field_role(text)


def _bounds(text):
    return len(text) - len(text.lstrip()), len(text.rstrip())


def _table_position(part):
    target = part.get('target', {})
    if target.get('kind') == 'csv':
        return ('csv',), target.get('row'), target.get('col'), 1
    if target.get('kind') == 'cell':
        return ('xlsx', target.get('sheet')), part.get('row'), part.get('column'), 1
    if part.get('tableContext'):
        c = part['tableContext']
        return ('word', c['name'], c['table']), c['row'], c['column'], c.get('columnSpan', 1)
    return None


def _name_value(value):
    if _normalize(value.strip('.')) in _PLACEHOLDERS:
        return False
    if re.fullmatch(r'[가-힣]{2,5}', value):
        return not re.search(r'(?:팀|부서|본부|센터|회사|담당)$', value)
    return bool(re.fullmatch(r"[A-ZÀ-ÖØ-Þ][a-zA-ZÀ-öø-ÿ'’.-]{0,29}(?:[ \t]+[A-ZÀ-ÖØ-Þ][a-zA-ZÀ-öø-ÿ'’.-]{0,29}){0,3}", value))


class FileContext:
    def __init__(self, parts):
        self.fields = {p['id']: [] for p in parts}
        self.values = {}
        self.pdf_labels = {}
        for part in parts:
            self._inline(part)
        self._tables(parts)
        self._pdf_rows(parts)
        self._adjacent_lines(parts)
        self._remember_organizations(parts)

    def _add(self, part, start, end, role):
        if start >= end:
            return
        field = Field(start, end, role)
        if field not in self.fields[part['id']]:
            self.fields[part['id']].append(field)
        value = part['text'][start:end]
        if role != 'label' and len(value) <= 100:
            self.values.setdefault(value, set()).add(role)

    def _value(self, part, start, end, role):
        value = part['text'][start:end]
        lo, hi = _bounds(value)
        if role in {'organization', 'ordinary', 'object'} and (
                hi - lo > 160 or ':' in value or '：' in value or _HUMAN_CUE.search(value)):
            return
        self._add(part, start + lo, start + hi, role)

    def _inline(self, part):
        text = part['text']; offset = 0
        for line in text.splitlines(keepends=True):
            matches = list(_INLINE.finditer(line))
            if matches:
                for i, match in enumerate(matches):
                    self._add(part, offset + match.start('label'), offset + match.end('label'), 'label')
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(line.rstrip('\r\n'))
                    # An unknown labelled subfield may contain a person's name.
                    self._value(part, offset + match.end(), offset + end, field_role(match['label']))
            elif match := _PLAIN.fullmatch(line.rstrip('\r\n')):
                self._add(part, offset + match.start('label'), offset + match.end('label'), 'label')
                self._value(part, offset + match.start('value'), offset + match.end('value'), field_role(match['label']))
            offset += len(line)

    def _tables(self, parts):
        tables = {}
        for part in parts:
            position = _table_position(part)
            if not position:
                continue
            table, row, col, span = position
            if isinstance(row, int) and isinstance(col, int):
                tables.setdefault(table, {}).setdefault(row, {}).setdefault(col, []).append(part)
        for rows in tables.values():
            headers = {}; previous = None
            for row, cells in sorted(rows.items()):
                if previous is not None and row != previous + 1:
                    headers.clear()
                previous = row
                texts = {col: '\n'.join(p['text'] for p in ps).strip() for col, ps in cells.items()}
                roles = {col: field_role(text) for col, text in texts.items()}
                # A full header row establishes column roles; a labelled row
                # establishes horizontal values. Never transfer across tables.
                if len(cells) > 1 and all(roles.values()):
                    headers.clear()
                    for col, ps in cells.items():
                        span = (_table_position(ps[0]) or (None, None, None, 1))[3]
                        if span == 1:
                            headers[col] = roles[col]
                        for part in ps:self._add(part, *_bounds(part['text']), 'label')
                    continue
                row_role = None; expected_col = None
                for col, ps in sorted(cells.items()):
                    role = roles[col]
                    span = _table_position(ps[0])[3]
                    if role:
                        for part in ps:self._add(part, *_bounds(part['text']), 'label')
                        row_role, expected_col = role, col + span
                        # A new form section must not inherit old column roles.
                        headers.clear()
                        continue
                    if expected_col is not None and col != expected_col:
                        row_role = None
                    role = row_role or headers.get(col)
                    if role:
                        for part in ps:self._value(part, 0, len(part['text']), role)
                    if row_role:expected_col = col + span

    def _pdf_rows(self, parts):
        """Only an explicit native label and its unambiguous same-row neighbour.

        No column/header propagation or name invention from PDF reading order.
        The original source parts and character positions remain independent.
        """
        from backend.detection_context import date_field_role
        pages={}
        for part in parts:
            if part.get('target',{}).get('kind')!='pdftext' or part.get('textLayerUncertain'):continue
            boxes=[b for b in part.get('boxes',[]) if b[2]>b[0] and b[3]>b[1]]
            if not boxes:continue
            rect=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
            pages.setdefault((part.get('asset'),part['target'].get('page')),[]).append((part,rect))
        for items in pages.values():
            width=max(rect[2] for _,rect in items)-min(rect[0] for _,rect in items)
            for label,left in items:
                role=field_role(label['text']);date_role=date_field_role(label['text'])
                if not date_role and role not in {'object','organization','ordinary'} and not (role or '').startswith('type:'):continue
                matches=[]
                for value,right in items:
                    if value['id']==label['id']:continue
                    gap=right[0]-left[2];height=min(left[3]-left[1],right[3]-right[1])
                    overlap=min(left[3],right[3])-max(left[1],right[1])
                    if 0<=gap<=width*.5 and height>0 and overlap/height>=.7 and abs((left[1]+left[3]-right[1]-right[3])/2)<=height*.3:
                        matches.append((gap,value))
                matches.sort(key=lambda item:item[0])
                if not matches or len(matches)>1 and matches[1][0]-matches[0][0]<1:continue
                value=matches[0][1]
                if field_role(value['text']) or date_field_role(value['text']) or len(value['text'])>200:continue
                self._add(label,*_bounds(label['text']),'label')
                self.pdf_labels[value['id']]=label['text']
                if role:self._value(value,0,len(value['text']),role)

    def _adjacent_lines(self, parts):
        # Explicit line indices only. OCR reading order and unrelated XML
        # paragraphs are not sufficient evidence for a detached label.
        lines = {p['target']['index']: p for p in parts if p.get('target', {}).get('kind') == 'line'}
        for i, part in lines.items():
            role = field_role(part['text'])
            if not role:
                continue
            following = lines.get(i + 1)
            if following and not field_role(following['text']) and not self.fields[following['id']]:
                self._add(part, *_bounds(part['text']), 'label')
                self._value(following, 0, len(following['text']), role)

    def _remember_organizations(self, parts):
        # Bare short words are deliberately never a document-wide exclusion.
        # Full organization phrases are reusable only without a role conflict.
        phrases = [v for v, roles in self.values.items() if roles == {'organization'} and
                   _ORG_SUFFIX.search(v) and 3 <= len(v) <= 100]
        phrases = sorted(phrases, key=len, reverse=True)[:500]
        if not phrases:
            return
        pattern = re.compile('|'.join(re.escape(value) for value in phrases))
        for part in parts:
            text = part['text']
            for match in pattern.finditer(text):
                before, after = text[:match.start()], text[match.end():]
                if before[-1:].isalnum():continue
                if after[:1].isalnum() and not re.match(r'(?:에서는|에는|에서|에게|으로|로|와|과|은|는|이|가|의|에)(?=$|[\s,.;:])', after):continue
                if any((f.role in {'person', 'ordinary', 'other'} or f.role.startswith('type:')) and f.start < match.end() and match.start() < f.end
                       for f in self.fields[part['id']]):continue
                self._add(part, match.start(), match.end(), 'organization')

    def refine(self, part, candidates):
        """Refine UTF-16 candidates for one original part; preserve other types."""
        text = part['text']; fields = self.fields[part['id']]
        if not fields:
            return candidates
        offsets = [0]
        for c in text:offsets.append(offsets[-1] + (2 if ord(c) > 0xffff else 1))
        valid_offsets = set(offsets); encoded = text.encode('utf-16-le')
        ranges = [(offsets[f.start], offsets[f.end], f) for f in fields]
        result = []
        for c in candidates:
            # Validate before filtering so malformed source positions cannot be
            # hidden by context. The caller supplies only fully mapped spans.
            if not 0 <= c['start'] < c['end'] or c['start'] not in valid_offsets or c['end'] not in valid_offsets or encoded[c['start']*2:c['end']*2].decode('utf-16-le') != c['text']:
                raise ValueError('Invalid candidate source span')
            if c['label'] in {'AGE', 'HEIGHT', 'WEIGHT'} and any(
                    f.role == 'object' and a <= c['start'] < c['end'] <= b for a,b,f in ranges):
                continue
            if c['label'] == 'PERSON':
                person = any(f.role == 'person' and a <= c['start'] < c['end'] <= b for a,b,f in ranges)
                excluded = any(f.role in {'label', 'organization', 'ordinary', 'object'} and a <= c['start'] < c['end'] <= b for a,b,f in ranges)
                if excluded and not person:
                    continue
                # Unfilled non-person fields are not names. Keep a literal
                # name in an explicit person field, even if it is the same word.
                placeholders = any(f.role != 'person' and f.role != 'label' and a <= c['start'] < c['end'] <= b
                    and _normalize(text[f.start:f.end]) in _PLACEHOLDERS for a,b,f in ranges)
                invalid_number_name = any(f.role.startswith('type:') and f.role[5:] in NUMERIC_LABELS | {'VEHICLE', 'DOC_ID'}
                    and a == c['start'] and c['end'] == b and any(ch.isdecimal() for ch in c['text']) for a,b,f in ranges)
                if not person and (placeholders or invalid_number_name):
                    continue
            result.append(c)
        for a, b, field in ranges:
            if not field.role.startswith('type:'):
                continue
            validated = field_detection(text[field.start:field.end], field.role[5:])
            if validated is None:
                continue
            start = offsets[field.start + validated.start]; end = offsets[field.start + validated.end]
            overlaps = [c for c in result if start < c['end'] and c['start'] < end]
            if any(c['label'] in CREDENTIAL_LABELS for c in overlaps):continue
            # Never replace a conflicting high-stakes identifier merely on a
            # field hint. Specific validated fields may displace fuzzy names.
            if any(c['risk'] == 'CRITICAL' and c['label'] != validated.label for c in overlaps):continue
            if any(c['start'] < start or c['end'] > end for c in overlaps):continue
            if len(overlaps) == 1 and overlaps[0]['label'] == validated.label and overlaps[0]['start'] == start and overlaps[0]['end'] == end:continue
            result = [c for c in result if c not in overlaps]
            from ko_pii.labels import LABEL_INFO
            result.append({'id':f'field-{validated.label}-{start}-{end}', 'source':'body', 'start':start, 'end':end,
                           'text':validated.text, 'label':validated.label,
                           'labelName':LABEL_INFO[validated.label][0], 'risk':validated.risk_level.name})
        for a, b, field in ranges:
            value = text[field.start:field.end]
            if field.role != 'person' or not _name_value(value):continue
            overlaps = [c for c in result if a < c['end'] and c['start'] < b]
            if any(c['label'] != 'PERSON' for c in overlaps):continue
            # Source labels and values must not be merged into a single name.
            if any(c['start'] < a and c['end'] > b for c in overlaps):continue
            if len(overlaps) == 1 and overlaps[0]['start'] == a and overlaps[0]['end'] == b:continue
            result = [c for c in result if c not in overlaps]
            result.append({'id':f'field-person-{a}-{b}', 'source':'body', 'start':a, 'end':b,
                           'text':value, 'label':'PERSON', 'labelName':'성명', 'risk':'HIGH'})
        return sorted(result, key=lambda c:(c['start'], c['end']))


def refine_result_fields(text, detections):
    """Use the same inline field policy for posts and files before overlap loss."""
    from ko_pii.core.types import DetectionResult, RiskLevel
    part = {'id':'body', 'text':text, 'target':{'kind':'text'}}
    context = FileContext([part])
    offsets = [0]
    for c in text:offsets.append(offsets[-1] + (2 if ord(c)>0xffff else 1))
    reverse = {value:index for index,value in enumerate(offsets)}
    originals = {str(i):d for i,d in enumerate(detections)}
    candidates = [{'id':i, 'source':'body', 'start':offsets[d.start], 'end':offsets[d.end],
                   'text':d.text, 'label':d.label, 'labelName':d.label, 'risk':d.risk_level.name}
                  for i,d in originals.items()]
    result = []
    for c in context.refine(part,candidates):
        if c['id'] in originals:
            result.append(originals[c['id']])
        else:
            result.append(DetectionResult(c['label'],c['text'],reverse[c['start']],reverse[c['end']],
                RiskLevel[c['risk']],.9,evidence=['context:validated_field']))
    return result
