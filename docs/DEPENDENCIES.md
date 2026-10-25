# Third party dependencies

## atonlee/koelectra-ko-pii-ner added 2026-10-17

`atonlee/koelectra-ko-pii-ner` is pinned at revision `1e75c01e707232401883cf364151bbe2e560c708`. Its model card declares Apache-2.0 for weights and attributes CC BY 4.0 training sources. The original model card is retained with the model. See [model attribution and integration details](features/model-a-integration.md#출처와-라이선스).

CPU inference uses torch 2.9.1+cpu (BSD-style, accompanying notices), transformers 4.57.6 (Apache-2.0), tokenizers 0.22.2 (Apache-2.0), safetensors 0.8.0 (Apache-2.0), and numpy 2.5.4 (BSD-3-Clause with bundled third-party notices). All additional versions are in `requirements.model-a.lock.txt`; keep the installed distribution license files when packaging. ONNX Runtime and GPU/CUDA packages are not part of this integration.

## Original application dependencies

Recorded 2026-10-16. Review full license terms before redistributing a packaged executable.

| Package | Version | License metadata |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| bottle | 0.13.4 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| clr_loader | 0.3.1 | See distribution license |
| colorama | 0.4.6 | See distribution license |
| fastapi | 0.143.2 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| ko-pii | 1.16.0 | MIT |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| proxy_tools | 0.1.0 | MIT |
| pycparser | 3.11 | BSD-3-Clause |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pytest | 9.1.1 | MIT |
| pythonnet | 3.2.1 | MIT |
| pywebview | 6.2.1 | BSD 3-Clause License |
| starlette | 1.8.0 | BSD-3-Clause |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

Frontend versions are pinned in package.json and pnpm-lock.yaml. React and React DOM use MIT; Vite uses MIT; TypeScript uses Apache-2.0. Keep their accompanying distribution notices when packaging.
