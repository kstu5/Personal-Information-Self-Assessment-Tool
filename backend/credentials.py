"""Local, source-bound credential detection. Never validate keys over a network.

Only field labels are normalized. Credential values, case and offsets stay
unchanged; OCR characters and wrapped tokens are never guessed or reconstructed.
"""
from dataclasses import replace
import math
import re
import unicodedata


LABEL = 'API_KEY'
LABEL_NAME = 'API 키·인증 토큰'
LABEL_NAMES = {LABEL: LABEL_NAME, 'PASSWORD': '비밀번호'}
CREDENTIAL_LABELS = frozenset(LABEL_NAMES)
CREDENTIAL_FIELD_LABELS = {
    'credential': ('API_KEY', 'API-KEY', 'APIKEY', 'API 키', '비밀 키', 'SECRET_KEY',
                   'SECRET KEY', 'CLIENT_SECRET', 'CLIENT SECRET', '클라이언트 시크릿',
                   'ACCESS_TOKEN', 'ACCESS TOKEN', '접근 토큰', '인증 토큰'),
    'credential:aws': ('AWS_SECRET_ACCESS_KEY', 'AWS SECRET ACCESS KEY', 'AWS SECRET KEY'),
    'credential:password': ('비밀번호', '비밀 번호', '패스워드', '암호', 'PASSWORD', 'PASSWD', 'PWD', 'PASSPHRASE'),
}


def _label(value):
    return re.sub(r'[\s_-]+', '', unicodedata.normalize('NFKC', value)).casefold()


_FIELD_ROLES = {_label(name): role for role, names in CREDENTIAL_FIELD_LABELS.items() for name in names}
_LABEL_TRANSLATE = str.maketrans({chr(i): chr(i - 0xfee0) for i in range(0xff01, 0xff5f)})
_LABEL_PATTERN = '|'.join(re.escape(name).replace(r'\ ', r'[ \t]*')
                          for name in sorted((n for ns in CREDENTIAL_FIELD_LABELS.values() for n in ns), key=len, reverse=True))
# Match labels on a separate comparison string, but keep every value in source.
_INLINE = re.compile(r'(?<![\w-])[\'\"]?(?P<label>' + _LABEL_PATTERN +
                     r')[\'\"]?[ \t]*[:=：][ \t]*', re.I)
_BARE_LABEL = re.compile(r'^[ \t\'\"]*(?P<label>' + _LABEL_PATTERN + r')[ \t\'\":：]*$', re.I)
_VALUE = re.compile(r'[\'\"]?(?P<value>[A-Za-z0-9_+/.=~\-]{16,256})(?![A-Za-z0-9_+/.=~\-])')
_AUTH = re.compile(r'(?i:authorization)[\'\"]?[ \t]*[:=：][ \t]*[\'\"]?(?i:bearer)[ \t]+')
# These formats are deliberately bounded. New provider formats require review.
_KNOWN = (
    ('GitHub', re.compile(r'(?:gh[pous]_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{76}|github_pat_[A-Za-z0-9_]{82})')),
    ('OpenAI', re.compile(r'sk-(?:(?:proj|svcacct|admin)-(?:[A-Za-z0-9_-]{74}|[A-Za-z0-9_-]{58})T3BlbkFJ(?:[A-Za-z0-9_-]{74}|[A-Za-z0-9_-]{58})|[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20})')),
    ('Stripe', re.compile(r'(?:sk|rk)_(?:test|live|prod)_[A-Za-z0-9]{10,99}')),
)
_PUBLIC_VALUE = re.compile(r'(?:pk_(?:test|live)_[A-Za-z0-9]+|(?:AKIA|ASIA)[A-Z2-7]{16})\Z')
_PLACEHOLDER = re.compile(r'(?:your[_-]?(?:api[_-]?)?key|your[_-]?token|replace[_-]?me|changeme|example|dummy|placeholder|insert[_-]?key(?:[_-]?here)?)', re.I)
_SERVICE_PASSWORD_LABEL = re.compile(r'[가-힣A-Za-z0-9._ -]{1,40}[ \t]+(?:비밀[ \t]*번호|패스워드|암호|password|passwd|pwd|passphrase)', re.I)
_PASSWORD_REFERENCE = re.compile(r'(?:\$\{[A-Za-z_][A-Za-z0-9_]*\}|\{\{[^{}\r\n]+\}\}|<(?:YOUR[_ -]?)?(?:PASSWORD|비밀번호|암호)>|\*{3,}|[•●█]{3,})', re.I)
_PASSWORD_INSTRUCTION = re.compile(r'(?:입력(?:하세요|해[ \t]*주세요)|변경(?:하세요|해[ \t]*주세요)|설정(?:하세요|해[ \t]*주세요)|재설정|별도[ \t]*안내|미입력|없음|비공개|해당[ \t]*없음|(?:please[ \t]+)?(?:enter|change|reset)[ \t]+(?:your[ \t]+)?password)[.!。]?', re.I)


def password_field_role(value):
    value = value.strip(' \t\r\n:：').translate(_LABEL_TRANSLATE)
    if _FIELD_ROLES.get(_label(value)) == 'credential:password' or _SERVICE_PASSWORD_LABEL.fullmatch(value):
        return 'credential:password'
    return None


def _password_span(text, start, end):
    """Read one literal source value, including quoted spaces and punctuation.

    No entropy/length-strength threshold: even one character can be a password.
    Preserve escapes and Unicode; never decode or reconstruct the source value.
    """
    while start < end and text[start] in ' \t':start += 1
    while end > start and text[end-1] in '\r\n':end -= 1
    if start == end:return None
    quote = {'"':'"', "'":"'", '“':'”', '‘':'’'}.get(text[start])
    if quote:
        lo = start + 1;hi = lo
        while hi < end:
            if text[hi] == '\\' and hi + 1 < end:
                hi += 2;continue
            if text[hi] == quote:break
            hi += 1
        if hi == end or hi == lo:return None
    else:
        if _PASSWORD_INSTRUCTION.fullmatch(text[start:end].strip()):return None
        lo = start;hi = lo
        while hi < end and not text[hi].isspace():hi += 1
    value = text[lo:hi]
    if not value or _PASSWORD_REFERENCE.fullmatch(value) or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff for c in value):return None
    return lo,hi


def _placeholder(value):
    if _PLACEHOLDER.fullmatch(value):
        return True
    # Explicit filler, not arbitrary low-entropy real credentials or prose.
    tail = re.sub(r'^(?:gh[pousr]_|github_pat_|(?:sk|rk|pk)_(?:test|live|prod)_)', '', value)
    return bool(re.fullmatch(r'[xX_\-]+', tail))


def _opaque(value):
    if _placeholder(value) or _PUBLIC_VALUE.fullmatch(value):
        return False
    if not re.fullmatch(r'[A-Za-z0-9_+/.=~\-]{16,256}', value):
        return False
    counts = {c: value.count(c) for c in set(value)}
    entropy = -sum((n / len(value)) * math.log2(n / len(value)) for n in counts.values())
    return len(counts) >= 8 and entropy >= 3


def inline_fields(text):
    """Return source value ranges and label roles, including one adjacent line."""
    result = []
    # Fullwidth ASCII label comparison is one-to-one. Values stay untouched.
    pos = 0
    pending = None
    for line in text.splitlines(keepends=True):
        comparison = line.translate(_LABEL_TRANSLATE)
        if pending is not None:
            start = len(line) - len(line.lstrip(' \t'))
            from backend.file_context import field_role
            next_label = re.match(r'[^:=：\r\n]{1,60}[:=：]', comparison)
            another_field = next_label and field_role(next_label[0].rstrip(':=：'))
            if not another_field and (_password_span(line,start,len(line)) if pending=='credential:password' else _VALUE.match(line, start)):
                result.append((pos + start, pos + len(line.rstrip('\r\n')), pending))
            pending = None
        matches = list(_INLINE.finditer(comparison))
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(line.rstrip('\r\n'))
            role = _FIELD_ROLES[_label(match['label'])]
            if line[start:end].strip():
                result.append((pos + start, pos + end, role))
            elif i == len(matches) - 1:
                pending = role
        if not matches:
            bare = _BARE_LABEL.fullmatch(comparison.rstrip('\r\n'))
            if bare:
                pending = _FIELD_ROLES[_label(bare['label'])]
            elif password_field_role(comparison.rstrip('\r\n')):
                pending = 'credential:password'
        pos += len(line)
    return result


def scan_credentials(text, fields=()):
    from ko_pii.core.types import DetectionResult, RiskLevel
    found = {}

    def add(start, end, provider, basis, label=LABEL):
        value = text[start:end]
        if not value or label == LABEL and _placeholder(value):
            return
        detail = {'provider': provider, 'basis': basis,
                  'reason': ('비밀번호 항목과 실제 입력 값을 연결해 확인했습니다. 길이·복잡도로 제외하지 않습니다.' if label=='PASSWORD' else
                             '알려진 비밀 키·토큰 형식과 일치합니다.' if basis == 'format' else
                             '인증정보 항목과 값의 형식을 함께 확인했습니다. 유효성은 확인하지 않았습니다.')}
        found.setdefault((start, end, label), DetectionResult(label, value, start, end, RiskLevel.HIGH,
                         .99 if basis == 'format' else .8, extra={'credential': detail}))

    for provider, pattern in _KNOWN:
        for match in pattern.finditer(text):
            # A URL query delimiter is a boundary; never clip a longer token.
            a, b = match.span()
            if a and re.match(r'[A-Za-z0-9_-]', text[a-1]):continue
            if b < len(text) and re.match(r'[A-Za-z0-9_-]', text[b]):continue
            add(a, b, provider, 'format')
    ranges = [*inline_fields(text), *fields]
    for match in _AUTH.finditer(text):
        end = text.find('\n', match.end())
        ranges.append((match.end(), end if end >= 0 else len(text), 'credential'))
    for a, b, role in ranges:
        if not 0 <= a <= b <= len(text):raise ValueError('Invalid credential field')
        if role=='credential:password':
            span = _password_span(text,a,b)
            if span:add(*span, '비밀번호', 'context', 'PASSWORD')
            continue
        lo = a + len(text[a:b]) - len(text[a:b].lstrip(' \t'))
        match = _VALUE.match(text, lo, b)
        if match is None:continue
        start, end = match.span('value');value = text[start:end]
        if not _opaque(value):continue
        # Public ids and visible examples do not override a known secret format.
        if role == 'credential:aws':
            if not re.fullmatch(r'[A-Za-z0-9/+=]{40}', value):continue
            add(start, end, 'AWS Secret Access Key', 'context')
        else:
            add(start, end, '일반 API 키·인증 토큰', 'context')
    return sorted(found.values(), key=lambda d: (d.start, d.end))


def merge_credentials(text, detections, fields=()):
    """Credential spans survive PII overlap resolution without leaking a suffix.

    Contained fuzzy PII is replaced. Crossing/containing spans are covered by a
    union so that adding a key detector cannot expose previously covered PII.
    """
    from ko_pii.core.overlap import resolve_overlaps
    existing = list(detections)
    discovered = scan_credentials(text, fields)
    if not discovered and not any(d.label in CREDENTIAL_LABELS for d in existing):return existing
    items = sorted([*existing, *discovered], key=lambda d:(d.start,d.end))
    groups = []
    for d in items:
        if not 0 <= d.start < d.end <= len(text) or text[d.start:d.end] != d.text:
            raise ValueError('Invalid credential merge source')
        if not groups or d.start >= groups[-1][0]:
            groups.append([d.end, [d]])
        else:
            groups[-1][0] = max(groups[-1][0], d.end)
            groups[-1][1].append(d)
    result = []
    for _, group in groups:
        keys = [d for d in group if d.label in CREDENTIAL_LABELS]
        if not keys:
            result.extend(resolve_overlaps(group));continue
        key = max(keys, key=lambda d:(d.label=='PASSWORD', (d.extra or {}).get('credential',{}).get('basis')=='format', d.confidence))
        a,b = min(d.start for d in group),max(d.end for d in group)
        extra = dict(key.extra)
        if (a,b) != (key.start,key.end):
            extra['credential'] = {**extra['credential'], 'reason': extra['credential']['reason'] + ' 겹치는 검출 영역도 함께 가립니다.'}
        result.append(replace(key, start=a, end=b, text=text[a:b],
                              risk_level=max(d.risk_level for d in group), extra=extra))
    return result


def review_credentials(text, detections, scopes=None):
    """Type-specific final context review; no PII model may veto credentials."""
    from backend.secondary_review import _window
    result = []
    for d in detections:
        if d.label not in CREDENTIAL_LABELS:
            result.append(d);continue
        if not 0 <= d.start < d.end <= len(text) or text[d.start:d.end] != d.text:
            raise ValueError('Invalid credential source')
        context, start, end, _ = _window(text, d, scopes)
        info = dict((d.extra or {}).get('credential', {}))
        if info.get('basis') not in {'format', 'context'}:
            raise ValueError('Missing credential evidence')
        # Only the target's own field can support it, never another row's key.
        local_fields = inline_fields(context)
        labelled = any(a <= start < end <= b for a,b,_ in local_fields)
        reason = info['reason']
        if info['basis'] == 'format' and labelled:
            reason += ' 주변의 인증정보 항목도 확인했습니다.'
        reason += (' 이미 공유한 비밀번호는 해당 서비스에서 변경하세요.' if d.label=='PASSWORD' else
                   ' 이미 공유한 키는 폐기·재발급을 검토하세요.')
        info['reason'] = reason
        result.append(replace(d, extra={**d.extra, 'credential':info,
            'contextReview': {'state':'supported' if info['basis']=='format' else 'uncertain',
                              'decision':'retain', 'reason':reason}}))
    return result
