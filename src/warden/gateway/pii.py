"""Find and mask personal data. Presidio if it is installed, regex if it is not.

Two jobs, two controls:
  W4 ingest scan   mask PII in a document BEFORE it is indexed, so the vector
                   store never holds a raw NI number or bank detail
  W6 output scan   catch PII on the way back to a caller who is not cleared

The UK identifiers Peoplecraft handles (National Insurance numbers, sort codes,
account numbers) are not in Presidio's default recognisers, so Warden adds
them as regex recognisers whether or not Presidio is present. That is the
honest lesson: a trained model helps with names and places, but the
identifiers that actually matter to a payroll firm are grammar you still have
to write yourself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from warden import constants as C


@dataclass
class Span:
    start: int
    end: int
    kind: str
    text: str


# region: pii_regexes
# UK-shaped identifiers, all restricted to fictional ranges in the corpus.
NINO_RE = re.compile(r"\b" + C.NINO_PREFIX + r"\d{6}[A-D]\b")
SORT_CODE_RE = re.compile(r"\b\d{2}-\d{2}-\d{2}\b")
ACCOUNT_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")
CARD_RE = re.compile(r"\b(?:\d[ -]?){15,16}\d\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b07\d{3}\s?\d{6}\b|\b07700\s?900\d{3}\b")
KEY_RE = re.compile(re.escape(C.FAKE_KEY_PREFIX) + r"[A-Za-z0-9_]*")

REGEX_KINDS = [
    ("KEY", KEY_RE),
    ("NINO", NINO_RE),
    ("CARD", CARD_RE),
    ("SORT_CODE", SORT_CODE_RE),
    ("EMAIL", EMAIL_RE),
    ("PHONE", PHONE_RE),
    ("ACCOUNT", ACCOUNT_RE),
]


def luhn_ok(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
# endregion: pii_regexes


# region: regex_engine
class RegexEngine:
    """The always-available engine. No model, no download, deterministic."""

    name = "regex"

    def find(self, text: str) -> list:
        spans = []
        taken = []
        for kind, pattern in REGEX_KINDS:
            for m in pattern.finditer(text):
                if kind == "CARD" and not luhn_ok(m.group(0)):
                    continue
                if any(m.start() < e and m.end() > s for s, e in taken):
                    continue          # do not double-claim an overlap
                taken.append((m.start(), m.end()))
                spans.append(Span(m.start(), m.end(), kind, m.group(0)))
        return sorted(spans, key=lambda s: s.start)
# endregion: regex_engine


class PresidioEngine:
    """Presidio plus the UK regex recognisers. Names and places come from the
    model; the payroll identifiers come from the regexes above."""

    name = "presidio"

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": C.SPACY_MODEL}],
        })
        self.analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())
        for kind, pattern in REGEX_KINDS:
            self.analyzer.registry.add_recognizer(PatternRecognizer(
                supported_entity="UK_" + kind,
                patterns=[Pattern(name=kind.lower(), regex=pattern.pattern, score=0.9)]))
        self._regex = RegexEngine()

    def find(self, text: str) -> list:
        spans = list(self._regex.find(text))
        taken = [(s.start, s.end) for s in spans]
        for r in self.analyzer.analyze(text=text, language="en"):
            if r.entity_type in ("PERSON", "LOCATION"):
                if any(r.start < e and r.end > s for s, e in taken):
                    continue
                taken.append((r.start, r.end))
                spans.append(Span(r.start, r.end, r.entity_type, text[r.start:r.end]))
        return sorted(spans, key=lambda s: s.start)


def get_engine(prefer_presidio: bool = True):
    """Presidio if importable, else the regex engine. Labelled either way."""
    if prefer_presidio:
        try:
            return PresidioEngine()
        except Exception:          # noqa: BLE001 - model or package absent
            return RegexEngine()
    return RegexEngine()


# region: mask
MASK_LABEL = {
    "KEY": "[API-KEY]", "NINO": "[NI-NUMBER]", "CARD": "[CARD]",
    "SORT_CODE": "[SORT-CODE]", "EMAIL": "[EMAIL]", "PHONE": "[PHONE]",
    "ACCOUNT": "[ACCOUNT]", "PERSON": "[NAME]", "LOCATION": "[PLACE]",
}


def mask(text: str, engine, kinds: set | None = None) -> tuple:
    """Return (masked_text, spans). `kinds` limits which entities are masked."""
    spans = [s for s in engine.find(text)
             if kinds is None or s.kind.replace("UK_", "") in kinds]
    out = text
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        label = MASK_LABEL.get(span.kind.replace("UK_", ""), "[REDACTED]")
        out = out[:span.start] + label + out[span.end:]
    return out, spans
# endregion: mask
