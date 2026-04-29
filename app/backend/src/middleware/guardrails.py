"""Guardrails: pre-flight content filters and PII redaction.

Phase 4 design choice: regex-based PII detection for the demo. In production
you'd use Microsoft Presidio, AWS Comprehend, or a similar NER-based detector.
The interface is small enough to swap implementations later.

Scope of redaction:
  - SSN, credit card, email, US phone numbers
Redaction is one-way: we replace with a placeholder and drop the original on
the floor before the prompt reaches the model. The audit log keeps only the
*type* of PII detected, never the value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Patterns are intentionally simple. They favor recall (catch obvious cases)
# over precision; tune per deployment.
_PATTERNS: dict[str, re.Pattern[str]] = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Visa/MC/Amex/Discover (loose; doesn't validate Luhn)
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone_us": re.compile(r"\b(?:\+?1[-. ]?)?(?:\(\d{3}\)|\d{3})[-. ]?\d{3}[-. ]?\d{4}\b"),
}


@dataclass
class GuardrailResult:
    text: str
    detected: list[str] = field(default_factory=list)
    redacted: bool = False


def redact_pii(text: str) -> GuardrailResult:
    """Redact known PII patterns. Returns the cleaned text + types detected."""
    detected: list[str] = []
    cleaned = text
    for label, pattern in _PATTERNS.items():
        if pattern.search(cleaned):
            detected.append(label)
            cleaned = pattern.sub(f"[REDACTED:{label.upper()}]", cleaned)
    return GuardrailResult(text=cleaned, detected=detected, redacted=bool(detected))


def apply_to_messages(messages: list, *, redact: bool = True) -> tuple[list, list[str]]:
    """Apply redaction to every text-content message. Returns (new_messages, detected_types)."""
    all_detected: list[str] = []
    new_messages = []
    for m in messages:
        m_copy = m.model_copy()
        if isinstance(m_copy.content, str):
            if redact:
                result = redact_pii(m_copy.content)
                if result.redacted:
                    all_detected.extend(result.detected)
                    m_copy.content = result.text
        new_messages.append(m_copy)
    # Dedupe while preserving order
    seen: set[str] = set()
    deduped = [d for d in all_detected if not (d in seen or seen.add(d))]
    return new_messages, deduped
