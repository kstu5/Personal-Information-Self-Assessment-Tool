# 직접 검사할 가상 예시

모두 합성 인적사항으로 만든 문서입니다. 실제 연락·발송에 사용하지 마세요. 안내문과 정답 목록은 검사 입력에서 제외합니다.

| 모음 | 구성 | 안내 |
|---|---|---|
| `documents/` | 이력서, 추첨 당첨자 명단, 참가자 안내, 회의록, 배송요청서 7개 | [사용 안내](documents/사용안내.md), [확인 목록](documents/검사_확인목록.md) |
| `formats/files/` | TXT·CSV·TSV·DOCX·PPTX·HWPX·HWP·XLSX·PDF·PNG·JPG·JPEG 12개 | [사용 안내](formats/사용안내.md), [확인 목록](formats/검사_확인목록.md) |

검출 건수와 정답 수는 다를 수 있습니다. 반복 위치·숨김 시트·메모·속성·노트도 확인하고, 부분 가림·직접 수정 후 실제 사본을 다시 확인하세요. 파일은 한 번에 8개 이하로 나눠 엽니다. 형식별 제한은 [미리보기 안내](../docs/features/file-preview-formats.md)에 있습니다.

제작·재현 스크립트는 `validation/_build/`, 회귀 입력은 `validation/fixtures/`에 있습니다. 예시 제작 도구는 앱 실행 환경과 별개이며 이미 완성된 파일을 검사할 때는 필요하지 않습니다. 상세 렌더링·로그·ZIP은 로컬 전용입니다. 재제작 방법은 [문서 검증 안내](../validation/README.md)를 참고하세요.
