"""Validated field values with normalization mapped back to untouched source.

This module does not repair digits or checksums. Numeric grouping is collapsed
only within one explicit field, and a detector must accept the complete value.
"""
from __future__ import annotations

from dataclasses import replace
import ipaddress
import re

# Static labels only; document values never enter shared state or a cache.
FIELD_LABELS = {
    'RRN': ('주민등록번호', '주민번호'),
    'FRN': ('외국인등록번호', '외국인번호'),
    'BUSINESS_REG': ('사업자등록번호',), 'CORP_REG': ('법인등록번호',),
    'DRIVER_LICENSE': ('운전면허번호', '면허번호'), 'PASSPORT': ('여권번호',),
    'CARD': ('카드번호',), 'PNU': ('토지번호', '필지고유번호'),
    'MEDICAL_INSURANCE': ('건강보험증번호', '의료보험증번호', '보험증번호'),
    'PRESCRIPTION_ID': ('처방번호', '처방전번호', '처방전 발행번호', 'Rx 번호'),
    'EDI_DRUG': ('약품코드', '의약품코드', 'KD코드', 'EDI'),
    'FAX': ('팩스', '팩스번호', 'FAX'), 'ACCOUNT': ('계좌번호', '계좌'),
    'EMPLOYEE_ID': ('사번', '직원번호', '사원번호', '임용번호'),
    'PETITION_ID': ('민원번호',), 'COURT_CASE': ('사건번호',),
    'PHONE': ('전화번호', '휴대전화', '휴대폰', '연락처', '전화', '핸드폰'),
    'EMAIL': ('이메일', 'Email'), 'IP': ('IP', 'IPv4', 'IPv6'), 'URL': ('URL',),
    'POSTAL_CODE': ('우편번호',), 'VEHICLE': ('차량번호',), 'DOC_ID': ('문서번호',),
    'NATIONALITY': ('국적',), 'EDUCATION': ('학력',), 'MAJOR': ('전공',),
    'POSITION': ('직책', '직위', '직급', '보직'),
    'HEIGHT': ('신장', '키'), 'WEIGHT': ('체중', '몸무게'), 'AGE': ('나이', '연령'),
}
NUMERIC_LABELS = frozenset({
    'RRN', 'FRN', 'BUSINESS_REG', 'CORP_REG', 'DRIVER_LICENSE', 'CARD', 'PNU',
    'MEDICAL_INSURANCE', 'FAX', 'ACCOUNT', 'EMPLOYEE_ID', 'PHONE', 'POSTAL_CODE',
})


def normalized_text(text):
    from ko_pii.core.unicode_norm import normalize_unicode
    return normalize_unicode(text)[0]


def valid_rule_span(text, detection):
    if detection.label == 'CORP_REG':
        digits = re.sub(r'\D', '', normalized_text(detection.text))
        if digits and not digits.strip('0'):
            return False
    if detection.label == 'IP' and ':' in detection.text:
        # Validate a whole contiguous IP token, not a valid suffix of a malformed
        # token such as 2001:zzzz::41. Brackets/whitespace delimit a real address.
        lo, hi = detection.start, detection.end
        allowed = lambda c: c.isascii() and (c.isalnum() or c in ':._%-')
        while lo and allowed(text[lo - 1]):lo -= 1
        while hi < len(text) and allowed(text[hi]):hi += 1
        token = text[lo:hi]
        token = normalized_text(token).strip('.')
        token = re.sub(r'^IP(?:v[46])?[:：]', '', token, flags=re.I)
        try:
            ipaddress.IPv6Address(token.split('%', 1)[0])
        except ValueError:
            return False
    return True


def _detector(label):
    from importlib import import_module
    names = {
        'RRN':'rrn', 'FRN':'frn', 'BUSINESS_REG':'business_reg', 'CORP_REG':'corp_reg',
        'DRIVER_LICENSE':'driver_license', 'PASSPORT':'passport', 'CARD':'card',
        'PNU':'pnu', 'MEDICAL_INSURANCE':'medical_insurance', 'PRESCRIPTION_ID':'prescription',
        'EDI_DRUG':'edi_drug', 'FAX':'fax', 'ACCOUNT':'account', 'COURT_CASE':'court_case',
        'PHONE':'phone', 'EMAIL':'email', 'IP':'ip', 'URL':'url', 'POSTAL_CODE':'postal_code',
        'VEHICLE':'vehicle', 'NATIONALITY':'nationality',
    }
    if label in names:
        return import_module('ko_pii.patterns.' + names[label]).detect
    if label in {'EDUCATION', 'MAJOR', 'POSITION', 'HEIGHT', 'WEIGHT', 'AGE'}:
        return import_module('ko_pii.patterns.personal_attr').detect
    domain = {'EMPLOYEE_ID':'hr', 'PETITION_ID':'civil_petition', 'DOC_ID':'government'}
    return import_module('ko_pii.domain.' + domain[label]).detect


def field_detection(value, label):
    """A full validated value, with Python offsets in original field text."""
    from ko_pii.core.unicode_norm import normalize_unicode, remap_to_source
    from ko_pii.labels import LABEL_INFO
    if label not in FIELD_LABELS or len(value) > 200:
        return None
    if label == 'IP' and value.rstrip().endswith('.'):
        # A sentence period is not part of the address. Validate the entire
        # preceding token, rather than accept a suffix of malformed IPv6.
        core = value.strip()
        try:ipaddress.ip_address(normalized_text(core[:-1]).split('%',1)[0])
        except ValueError:pass
        else:
            found = field_detection(core[:-1], label)
            if found is not None:
                shift = len(value)-len(value.lstrip())
                return replace(found,start=found.start+shift,end=found.end+shift)
    # Canonical keyword is detector evidence, not source text or an edit target.
    prefix = LABEL_INFO[label][0] + ': '
    source = prefix + value
    normalized, mapping = normalize_unicode(source)
    mapping = mapping or list(range(len(source)))
    begin = len(prefix); lo = len(value) - len(value.lstrip()); hi = len(value.rstrip())
    views = [(normalized, mapping)]
    if label in NUMERIC_LABELS:
        tail = normalized[len(prefix):]
        if re.fullmatch(r'[0-9 \t./-]+', tail):
            keep = [i for i,c in enumerate(normalized) if i < len(prefix) or c.isdigit()]
            compact = ''.join(normalized[i] for i in keep)
            if compact != normalized:views.append((compact, [mapping[i] for i in keep]))
    for view, offsets in views:
        for d in _detector(label)(view):
            if d.label != label:
                continue
            original = remap_to_source([d], offsets, source)[0]
            if original.start != begin + lo or original.end != begin + hi:
                continue
            if not valid_rule_span(source, original):
                continue
            return replace(original, start=lo, end=hi, text=value[lo:hi],
                           evidence=[*original.evidence, 'context:validated_field'])
    return None


def rule_detections(text):
    from ko_pii import detect_all
    return [d for d in detect_all(text) if valid_rule_span(text, d)]
