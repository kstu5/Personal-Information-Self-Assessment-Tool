import pytest

from ko_pii.core.types import DetectionResult, RiskLevel
from backend.detection_context import refine_detections
from backend.detection import detect_document


def span(text, value, label, risk=RiskLevel.HIGH):
    start = text.index(value)
    return DetectionResult(label, value, start, start + len(value), risk, .9)


@pytest.mark.parametrize('prefix', ['작성일:', '발송 예정일 ', '회의 일시 ', '행사 일자 ', '발표일\n\n', '면접일은 '])
def test_explicit_schedule_date_is_not_a_birthday(prefix):
    text = prefix + '2024년 8월 9일 윤지후'
    assert refine_detections(text, [span(text, '2024년 8월 9일', 'DT_BIRTH')]) == []


@pytest.mark.parametrize('text,value', [
    ('작성일: 2024.08.09 생년월일: 1991.02.06', '1991.02.06'),
    ('작성일: 2024.08.09\n\n성명 윤지후\n\n1991.02.06', '1991.02.06'),
    ('생년월일\n\n1991년 2월 6일 지원자 윤지후', '1991년 2월 6일'),
    ('DOB: 1991-02-06 작성자 윤지후', '1991-02-06'),
    ('윤지후 1991년 2월 6일', '1991년 2월 6일'),
    ('작성일 1991년 2월 6일생', '1991년 2월 6일'),
    ('작성일 확인 후 1991년생 윤지후', '1991년생'),
    ('출생연월일\n\n1991-02-06 서명 윤지후', '1991-02-06'),
])
def test_explicit_or_ambiguous_birthday_is_preserved(text, value):
    found = refine_detections(text, [span(text, value, 'DT_BIRTH')])
    assert [(d.label, d.text) for d in found] == [('DT_BIRTH', value)]


def test_signature_date_is_removed_without_removing_nearby_name_or_real_birthday():
    text = '생년월일 1991-02-06\n\n2024년 8월 9일 신청인 윤지후'
    found = refine_detections(text, [span(text, '1991-02-06', 'DT_BIRTH'),
        span(text, '2024년 8월 9일', 'DT_BIRTH'), span(text, '윤지후', 'PERSON')])
    assert [(d.label, d.text) for d in found] == [('DT_BIRTH', '1991-02-06'), ('PERSON', '윤지후')]


@pytest.mark.parametrize('address,predicted', [
    ('울산광역시 남구 새연구로 7-3, 105동 204호', '울산광역시 남구 새연구로 7-3, 105동 204'),
    ('세종특별자치시 한누리대로 9, 3층', '세종특별자치시 한누리대로 9'),
    ('전라남도 순천시 새연구길 8, 405호', '전라남도 순천시 새연구길 8, 405'),
])
def test_address_units_extend_without_swallowing_next_contact(address, predicted):
    text = address + ' 전화 010-0000-1111'
    found = refine_detections(text, [span(text, predicted, 'ADDRESS', RiskLevel.MEDIUM), span(text, '010-0000-1111', 'PHONE')])
    assert [(d.label, d.text) for d in found] == [('ADDRESS', address), ('PHONE', '010-0000-1111')]


def test_extension_does_not_cross_fields_or_override_an_existing_higher_risk_span():
    text = '서울특별시 새연구로 7\n\n204호'
    assert refine_detections(text, [span(text, '서울특별시 새연구로 7', 'ADDRESS')])[0].text == '서울특별시 새연구로 7'
    text = '서울특별시 새연구로 7, 204호'
    found = refine_detections(text, [span(text, '서울특별시 새연구로 7', 'ADDRESS', RiskLevel.MEDIUM), span(text, '204', 'RRN', RiskLevel.CRITICAL)])
    assert [(d.label, d.text) for d in found] == [('ADDRESS', '서울특별시 새연구로 7'), ('RRN', '204')]


def test_labelled_road_fragments_are_joined_without_masking_the_label():
    address = '울산광역시 남구 새연구로 7-3, 105동 204호'
    text = '😀 장소  ' + address + '\n공개 안내는 유지'
    found = refine_detections(text, [span(text, '광역시', 'ADDRESS', RiskLevel.MEDIUM), span(text, '로 7', 'ADDRESS', RiskLevel.MEDIUM)])
    assert len(found) == 1 and found[0].text == address
    assert text[found[0].start:found[0].end] == address
    class Engine:
        name = 'offset verification'
        def detect(self, value):
            return refine_detections(value, [span(value, '광역시', 'ADDRESS', RiskLevel.MEDIUM), span(value, '로 7', 'ADDRESS', RiskLevel.MEDIUM)]) if value else []
    candidate = detect_document('', text, Engine())['candidates'][0]
    assert text.encode('utf-16-le')[candidate['start']*2:candidate['end']*2].decode('utf-16-le') == address


def test_context_does_not_invent_an_address_or_expand_unlabelled_fragments():
    text = '장소 울산광역시 남구 새연구로 7-3'
    assert refine_detections(text, []) == []
    text = '울산광역시 남구 새연구로 7-3'
    assert refine_detections(text, [span(text, '광역시', 'ADDRESS')])[0].text == '광역시'
    text = '장소 서울시 행사로 10주년 안내'
    assert refine_detections(text, [span(text, '서울시', 'ADDRESS')])[0].text == '서울시'


def test_purpose_descriptor_is_filtered_but_real_names_and_short_latin_names_remain():
    text = '윤지후_배포용_목록\nLi\n공유\nPython'
    found = refine_detections(text, [span(text, '윤지후', 'PERSON'), span(text, '배포용', 'PERSON'),
        span(text, 'Li', 'PERSON'), span(text, '공유', 'PERSON'), span(text, 'th', 'PERSON')])
    assert [d.text for d in found] == ['윤지후', 'Li', '공유']


@pytest.mark.parametrize('text,kept', [
    ('업무 역량 Python', False), ('기술 스택 JavaScript', False),
    ('프로그래밍 언어 SQL', False), ('성명 Python', True),
    ('기술 스택 SQL 담당자 Java', True), ('업무 역량\nPython', True),
])
def test_technology_words_require_local_skill_context_before_filtering(text,kept):
    value=text.split()[-1]
    assert bool(refine_detections(text, [span(text, value, 'PERSON')])) is kept
