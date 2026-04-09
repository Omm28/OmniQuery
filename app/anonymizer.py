"""
PII Anonymization module — powered by Microsoft Presidio.

Usage:
    from app.anonymizer import anonymize, deanonymize

    anon_text, mapping = anonymize("Call me at 555-1234 or email john@example.com")
    # anon_text  → "Call me at <PHONE_NUMBER> or email <EMAIL_ADDRESS>"
    # mapping    → {"<PHONE_NUMBER>": "555-1234", "<EMAIL_ADDRESS>": "john@example.com"}

    restored = deanonymize(agent_reply, mapping)
    # Replaces placeholders back with the originals in the agent's response.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

log = logging.getLogger(__name__)

# ── Engine singletons (loaded once at import time) ────────────────────────────
_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "US_SSN",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_ITIN",
    "US_PASSPORT",
    "MEDICAL_LICENSE",
    "URL",
    "LOCATION",
]

_SCORE_THRESHOLD = 0.5

def anonymize(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Detect and replace PII in *text* with stable placeholders.

    The placeholders are formatted as ``<ENTITY_TYPE>`` with an incrementing
    counter for repeated entity types, e.g.::

        <EMAIL_ADDRESS_1>, <EMAIL_ADDRESS_2>, <PHONE_NUMBER_1>

    Returns
    -------
    anonymized_text : str
        The text with PII replaced by placeholders.
    mapping : dict[str, str]
        ``{placeholder: original_value}`` so the caller can later restore PII
        in the agent's response via :func:`deanonymize`.
    """
    if not text or not text.strip():
        return text, {}

    results: list[RecognizerResult] = _analyzer.analyze(
        text=text,
        language="en",
        entities=_ENTITIES,
        score_threshold=_SCORE_THRESHOLD,
    )

    if not results:
        return text, {}

    
    results.sort(key=lambda r: r.start, reverse=True)

    
    counters: Dict[str, int] = {}
    mapping: Dict[str, str] = {}
    anonymized = text

    for result in results:
        entity = result.entity_type
        counters[entity] = counters.get(entity, 0) + 1
        placeholder = f"<{entity}_{counters[entity]}>"

        original = text[result.start:result.end]
        mapping[placeholder] = original

        anonymized = anonymized[: result.start] + placeholder + anonymized[result.end :]

    log.info(
        "anonymizer | detected %d PII entities | types=%s",
        len(results),
        sorted({r.entity_type for r in results}),
    )
    return anonymized, mapping

def deanonymize(text: str, mapping: Dict[str, str]) -> str:
    """
    Restore PII placeholders in *text* using the ``mapping`` from :func:`anonymize`.

    If the agent's response never echoed a placeholder the result is returned
    unchanged — this is always safe to call even when ``mapping`` is empty.

    Example
    -------
    >>> deanonymize("Send a reply to <EMAIL_ADDRESS_1>", {"<EMAIL_ADDRESS_1>": "john@example.com"})
    'Send a reply to john@example.com'
    """
    if not mapping:
        return text

    result = text
    for placeholder, original in mapping.items():
        result = result.replace(placeholder, original)

    return result
