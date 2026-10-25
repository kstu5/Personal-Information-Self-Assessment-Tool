"""Offline CPU inference, using the windowing policy verified in the A/B benchmark."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from backend.model_assets import MODEL_DIR, verify_model

DELEGATED_LABELS = frozenset({'PERSON', 'ADDRESS'})
LABEL_MAP = {'NAME': 'PERSON', 'ADDRESS': 'ADDRESS'}


def decode_spans(text, tokens, id2label):
    """Decode BIO after choosing one prediction for each original token offset."""
    from ko_pii.core.types import DetectionResult, RiskLevel
    spans, active = [], None

    def finish():
        nonlocal active
        if active is not None:
            label, start, end, scores = active
            spans.append(DetectionResult(
                label=label, text=text[start:end], start=start, end=end,
                risk_level=RiskLevel.HIGH if label == 'PERSON' else RiskLevel.MEDIUM,
                confidence=sum(scores) / len(scores),
            ))
        active = None

    for (start, end), (_, ident, score) in sorted(tokens.items()):
        tag = id2label[ident]
        if tag == 'O' or tag[2:] not in LABEL_MAP:
            finish()
            continue
        label = LABEL_MAP[tag[2:]]
        if tag.startswith('B-') or active is None or active[0] != label:
            finish()
            active = [label, start, end, [score]]
        else:
            active[2] = end
            active[3].append(score)
    finish()
    return spans


class ModelA:
    def __init__(self, path: Path = MODEL_DIR):
        verify_model(path)
        # Set these before importing Hugging Face. Loading is local-only as well.
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                          HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false')
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
        self.torch = torch
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        # A process owns one model for its lifetime.
        torch.set_num_interop_threads(1)
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False, use_fast=True)
        self.model, loading = AutoModelForTokenClassification.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False,
            use_safetensors=True, dtype=torch.float32, output_loading_info=True)
        if any(loading.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
            raise ValueError('Model weights do not match the architecture')
        if not self.tokenizer.is_fast or self.model.config.max_position_embeddings < 512:
            raise ValueError('Unsupported tokenizer or model context')
        self.model.to('cpu').eval()

    def detect(self, text: str):
        if not text.strip():
            return []
        encoded = self.tokenizer(
            text, truncation=True, max_length=512, stride=64,
            return_overflowing_tokens=True, return_offsets_mapping=True,
            return_special_tokens_mask=True, padding=False)
        tokens = {}
        torch = self.torch
        with torch.inference_mode():
            for window in range(len(encoded['input_ids'])):
                inputs = {key: torch.tensor([encoded[key][window]], dtype=torch.long)
                          for key in ('input_ids', 'attention_mask', 'token_type_ids') if key in encoded}
                probabilities = torch.softmax(self.model(**inputs).logits[0], dim=-1)
                values, labels = probabilities.max(dim=-1)
                offsets = encoded['offset_mapping'][window]
                for index, ((start, end), special) in enumerate(zip(offsets, encoded['special_tokens_mask'][window])):
                    if special or start == end:
                        continue
                    # Overlap gives boundary tokens more context; ties use the first window.
                    centrality = min(index, len(offsets) - 1 - index)
                    if (start, end) not in tokens or centrality > tokens[(start, end)][0]:
                        tokens[(start, end)] = (centrality, int(labels[index]), float(values[index]))
        return decode_spans(text, tokens, self.model.config.id2label)


class HybridDetector:
    def __init__(self, path: Path = MODEL_DIR):
        self.model = ModelA(path)
        from ko_pii import __version__
        self.name = f'ko-pii {__version__} + A 모델 (이름·주소)'

    def detect(self, text: str):
        from ko_pii import detect_all
        from ko_pii.integrations.hybrid import MergeMode, merge_detections
        from backend.detection_context import refine_detections
        merged = merge_detections(detect_all(text), self.model.detect(text),
                                  mode=MergeMode.ROLE_SPLIT, role_split_labels=DELEGATED_LABELS)
        return refine_detections(text, merged)
