"""Offline CPU inference, using the windowing policy verified in the A/B benchmark."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from backend.model_assets import MODEL_DIR, MODEL_REPO, verify_model

DELEGATED_LABELS = frozenset({'PERSON', 'ADDRESS'})
LABEL_MAP = {'NAME': 'PERSON', 'ADDRESS': 'ADDRESS'}
CONTEXT_LABEL_MAP = {**LABEL_MAP, 'DATE': 'GENERAL_DATE',
                     'BIRTHDATE': 'MODEL_BIRTHDATE', 'ORGANIZATION': 'ORGANIZATION'}


def decode_spans(text, tokens, id2label, label_map=None):
    """Decode BIO after choosing one prediction for each original token offset."""
    from ko_pii.core.types import DetectionResult, RiskLevel
    spans, active = [], None
    label_map = LABEL_MAP if label_map is None else label_map

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
        if tag == 'O' or tag[2:] not in label_map:
            finish()
            continue
        label = label_map[tag[2:]]
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
        return [d for d in self.analyze(text) if d.label in DELEGATED_LABELS]

    def analyze(self, text: str):
        """Retain supporting labels from the same forward pass; no document cache."""
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
        return decode_spans(text, tokens, self.model.config.id2label, CONTEXT_LABEL_MAP)

    def analyze_many(self, texts):
        """Re-read independent candidate contexts in bounded CPU batches."""
        if not texts:return []
        encoded=self.tokenizer(texts,truncation=True,max_length=512,stride=64,
            return_overflowing_tokens=True,return_offsets_mapping=True,
            return_special_tokens_mask=True,padding=True)
        samples=encoded['overflow_to_sample_mapping'];tokens=[{} for _ in texts]
        torch=self.torch
        with torch.inference_mode():
            for lo in range(0,len(samples),8):
                hi=min(lo+8,len(samples))
                inputs={k:torch.tensor(encoded[k][lo:hi],dtype=torch.long)
                        for k in ('input_ids','attention_mask','token_type_ids') if k in encoded}
                values,labels=torch.softmax(self.model(**inputs).logits,dim=-1).max(dim=-1)
                for row,window in enumerate(range(lo,hi)):
                    target=tokens[samples[window]]
                    length=sum(encoded['attention_mask'][window])
                    for i,((start,end),special) in enumerate(zip(encoded['offset_mapping'][window],encoded['special_tokens_mask'][window])):
                        if special or start==end or not encoded['attention_mask'][window][i]:continue
                        centrality=min(i,length-1-i)
                        if (start,end) not in target or centrality>target[(start,end)][0]:
                            target[(start,end)]=(centrality,int(labels[row,i]),float(values[row,i]))
        return [decode_spans(t,ts,self.model.config.id2label,CONTEXT_LABEL_MAP) for t,ts in zip(texts,tokens)]


class HybridDetector:
    def __init__(self, path: Path = MODEL_DIR):
        self.model = ModelA(path)
        from backend.qwen_runtime import selected_secondary
        self.secondary = selected_secondary()
        self.qwen = None
        from ko_pii import __version__
        self.name = f'ko-pii {__version__} + {MODEL_REPO} (이름·주소)'
        if self.secondary == 'qwen3.5-0.8b':
            from backend.qwen_review import QwenReviewer
            self.qwen = QwenReviewer()
            self.name += ' + Qwen3.5-0.8B (2차 문맥 검토)'

    def close(self):
        if self.qwen is not None:
            self.qwen.close()

    def detect(self, text: str):
        return self.review(text,self.detect_primary(text))

    def detect_primary(self, text: str):
        from backend.identifier_rules import rule_detections
        from backend.detection_context import refine_detections
        # Keep role splitting, but resolve overlaps after explicit field checks.
        # Otherwise a fuzzy name can discard a valid whole document identifier.
        merged = [d for d in rule_detections(text) if d.label not in DELEGATED_LABELS]
        reading = self.model.analyze(text)
        merged.extend(d for d in reading if d.label in DELEGATED_LABELS)
        return refine_detections(text, merged, model_spans=reading)

    def review(self,text,detections,scopes=None):
        if getattr(self, 'qwen', None) is not None:
            return self.qwen.review(text, detections, scopes)
        from backend.secondary_review import review_candidates
        analyze=getattr(self.model,'analyze_many',None)
        if analyze is None:analyze=lambda texts:[self.model.analyze(t) for t in texts]
        return review_candidates(text,detections,analyze,scopes)
