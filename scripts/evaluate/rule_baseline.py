"""Frozen rule-only adapter for the October 16 diagnostic scripts."""
from backend.detection import detect_document as format_document


class RuleBaseline:
    name = 'ko-pii 1.16.0 (규칙 기준선)'

    @staticmethod
    def detect(text):
        from ko_pii import detect_all
        return detect_all(text)


def detect_document(title, body):
    return format_document(title, body, RuleBaseline())
