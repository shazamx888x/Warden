"""The chapter order, defined once.

Chapter numbers are never typed into prose. Prose calls ref("cloudflare") and
gets the right number; move a chapter and every reference follows. This is the
mechanism that stopped a guide in this series shipping four wrong chapter
numbers in one table.
"""

from __future__ import annotations

CHAPTERS: list[tuple[str, str]] = [
    ("intro", "How to use this guide"),
    ("problem", "The one question"),
    ("setup", "Set up and make the corpus"),
    ("target", "Build the HR Assistant"),
    ("break", "Break it"),
    ("gateway", "Warden: one gateway in front of any app"),
    ("rules", "W1 and W2: fast rules and the injection classifier"),
    ("harm", "W3: the harmful content check"),
    ("ingest", "W4: scan and mask documents before indexing"),
    ("permission", "W5: permission-aware retrieval"),
    ("output", "W6 and W7: output scan and the canary"),
    ("tools", "W8: the tool-call policy engine"),
    ("assemble", "Put the gateway together"),
    ("redteam", "Red teaming: measuring it honestly"),
    ("cloudflare", "Ship it to Cloudflare"),
    ("ci", "The gate: red teaming on every change"),
    ("cost", "Cost, and what is left"),
    ("sell", "What you can sell from this"),
]

APPENDICES: list[tuple[str, str]] = [
    ("A", "The offline simulator, and why it is honest"),
    ("B", "How Warden relates to AegisAI"),
    ("C", "OWASP LLM Top 10 coverage"),
    ("D", "When Warden does not work"),
    ("E", "Glossary"),
]

NUMBER = {key: index for index, (key, _) in enumerate(CHAPTERS, start=1)}
TITLE = dict(CHAPTERS)

LAST_OFFLINE_CHAPTER = "redteam"
FIRST_CLOUD_CHAPTER = "cloudflare"


def n(key: str) -> int:
    if key not in NUMBER:
        raise KeyError("no chapter named {!r}. Chapters: {}".format(
            key, ", ".join(NUMBER)))
    return NUMBER[key]


def ref(key: str) -> str:
    return "chapter {}".format(n(key))


def ref_range(first: str, last: str) -> str:
    return "chapters {} to {}".format(n(first), n(last))


def offline_range() -> str:
    return ref_range(CHAPTERS[0][0], LAST_OFFLINE_CHAPTER)


def cloud_range() -> str:
    return ref_range(FIRST_CLOUD_CHAPTER, CHAPTERS[-1][0])
