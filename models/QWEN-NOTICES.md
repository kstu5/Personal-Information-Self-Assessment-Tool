# 선택 모델 및 실행 도구

Qwen 기능은 기본 설치에 모델을 추가하지 않습니다. 사용자가 준비 스크립트를 실행할 때 다음 배포물을 내려받습니다. 버전·파일 크기·SHA-256은 `qwen-review.json`에 고정하며 실행 전에 검증합니다.

| 구성요소 | 출처 | 라이선스 |
|---|---|---|
| 원 모델 Qwen3.5-0.8B | [Qwen](https://huggingface.co/Qwen/Qwen3.5-0.8B) | [Apache License 2.0](https://huggingface.co/Qwen/Qwen3.5-0.8B/blob/main/LICENSE) |
| Q4_K_M GGUF 변환본 | [Unsloth](https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/tree/6ab461498e2023f6e3c1baea90a8f0fe38ab64d0) | Apache License 2.0 |
| llama.cpp Windows CPU x64 | [b11960 배포물](https://github.com/ggml-org/llama.cpp/releases/tag/b11960) | [MIT](https://github.com/ggml-org/llama.cpp/blob/b11960/LICENSE) |
| LLVM OpenMP 실행 구성요소 | 위 llama.cpp 압축 파일에 포함 | 압축 파일의 `LICENSE-LLVM-OpenMP` 참조 |

프로젝트는 재학습한 가중치를 제공하지 않습니다. GGUF는 원 모델의 양자화 배포물이며 원본 정밀도와 성능이 같다고 보장하지 않습니다. 모델 입력에는 기존 OCR·문서 추출기가 읽은 텍스트만 사용합니다. 이 기능의 시험 결과는 프로젝트 전체 또는 일반 문서에 대한 개인정보 검출 정확도를 보장하지 않습니다.
