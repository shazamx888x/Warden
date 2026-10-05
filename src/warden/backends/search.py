"""Retrieval, offline and on Cloudflare Vectorize.

The offline index is a deterministic bag of words store: no model download, no
network, same ranking on every machine. It carries each document's `acl_group`
as metadata, which is the field the permission filter (control W5) matches on,
exactly as a Vectorize metadata index would.

The point of keeping the acl_group ON the stored record, rather than filtering
after retrieval, is that on Cloudflare the filter runs INSIDE the query. A
design that filters after the fact cannot be pushed to the edge, and a control
the platform cannot enforce is one that gets dropped under deadline.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from warden import constants as C


@dataclass
class Hit:
    doc_id: str
    title: str
    text: str
    acl_group: str
    source: str
    doc_type: str
    department: str = ""
    is_hostile: bool = False
    score: float = 0.0


STOPWORDS = {
    "the", "and", "for", "you", "your", "our", "with", "that", "this", "are",
    "was", "can", "will", "have", "has", "from", "they", "them", "their",
    "what", "who", "how", "why", "when", "where", "show", "give", "list",
    "please", "tell", "about", "into", "out", "all", "any", "every", "everyone",
    "some", "one", "two", "get", "got", "let", "see", "make", "made", "does",
    "did", "not", "but", "his", "her", "its", "me", "my", "we", "us", "it",
    "is", "in", "of", "to", "on", "or", "an", "as", "at", "be", "by", "so",
    "up", "do", "if", "no", "am", "he", "say", "said",
}


def _stem(word: str) -> str:
    """A tiny stemmer so 'salaries' and 'salary' match, the way a real vector
    search would. Not linguistics, just enough to stop the offline keyword
    index being more literal than the embedding model it stands in for."""
    for suffix in ("ies", "ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            base = word[: -len(suffix)]
            return base + "y" if suffix == "ies" else base
    return word


# "salary" is the distinctive token for pay records, so a query that says
# "salaries" or "remuneration" should reach them. "pay" is deliberately NOT
# mapped: it appears in benign policies ("sick pay") and mapping it would drag
# those into every salary search.
SYNONYMS = {"salaries": "salary", "remuneration": "salary",
            "staff": "employee", "worker": "employee", "workers": "employee"}


def tokenise(text: str) -> list:
    out = []
    for w in re.findall(r"[a-z0-9]{2,}", text.lower()):
        if w in STOPWORDS:
            continue
        out.append(_stem(SYNONYMS.get(w, w)))
    return out


# region: local_index
class LocalIndex:
    """A seeded, offline vector-store stand-in with metadata filtering."""

    def __init__(self, corpus: str | Path | None = None, records: list | None = None):
        self.records: list = []
        if records is not None:
            for r in records:
                self.add(r)
        elif corpus is not None:
            with Path(corpus).open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        self.add(json.loads(line))

    def add(self, record: dict) -> None:
        counts = Counter(tokenise(record["title"] + " " + record["text"]))
        self.records.append((record, counts))

    def plant(self, record: dict) -> None:
        """Add one document to a query-time copy of the index (red team use)."""
        self.add(record)

    def clone(self) -> "LocalIndex":
        """A shallow copy sharing the token counts, for one-probe-at-a-time
        isolation: a base index built once, then one hostile document planted
        per probe, so probes cannot contaminate each other."""
        copy = LocalIndex()
        copy.records = list(self.records)
        return copy

    def _idf(self) -> dict:
        """Inverse document frequency, so a rare word like a department name
        counts for more than a word like 'salary' that is in every payslip.
        Without this the offline index is more literal than the embedding
        model it stands in for, and salary questions surface policy pages
        instead of the register that actually answers them."""
        n = len(self.records)
        df = Counter()
        for _, counts in self.records:
            for token in counts:
                df[token] += 1
        return {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}

    def query(self, question: str, allowed_groups: list | None, top_k: int) -> list:
        """Nearest documents. If allowed_groups is given, filter to them FIRST.

        The filter is applied before ranking, the way a Vectorize $in filter is
        applied inside the query, so a document the caller may not read never
        competes for a slot and never reaches the model.
        """
        # Normalise the query the way the model reads it (decode base64, strip
        # zero width) BEFORE tokenising, so an obfuscated request retrieves the
        # documents it is really asking for. A naive pipeline that skipped this
        # would just fail to answer, which would hide the attack rather than
        # letting it land and be measured.
        from warden.backends.offline_llm import normalise_for_model

        idf = self._idf()
        wanted = Counter({t: c * idf.get(t, 1.0)
                          for t, c in Counter(
                              tokenise(normalise_for_model(question))).items()})
        allow = set(allowed_groups) if allowed_groups is not None else None
        scored = []
        for record, counts in self.records:
            if allow is not None and record["acl_group"] not in allow:
                continue
            weighted = Counter({t: c * idf.get(t, 1.0) for t, c in counts.items()})
            score = self._cosine(wanted, weighted)
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["doc_id"]))
        hits = []
        for score, record in scored[:top_k]:
            hits.append(Hit(
                doc_id=record["doc_id"], title=record["title"],
                text=record["text"], acl_group=record["acl_group"],
                source=record["source"], doc_type=record["doc_type"],
                department=record.get("department", ""),
                is_hostile=record.get("is_hostile", False), score=round(score, 4)))
        return hits

    @staticmethod
    def _cosine(a: Counter, b: Counter) -> float:
        common = set(a) & set(b)
        if not common:
            return 0.0
        dot = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0
# endregion: local_index


# ---------------------------------------------------------------------------
# Cloudflare Vectorize. VERIFIED against docs on constants.DOCS_CHECKED_DATE,
# NOT yet run. The acl_group filter uses $in, the operator the metadata index
# supports, and the metadata index must be created BEFORE vectors are upserted
# or they are not filterable (a documented Vectorize gotcha).
# ---------------------------------------------------------------------------
class VectorizeIndex:
    name = "cloudflare"

    def __init__(self) -> None:
        self.account = os.environ["CF_ACCOUNT_ID"]
        self.token = os.environ["CF_API_TOKEN"]
        self.index = os.environ.get("CF_VECTORIZE_INDEX", C.CF_VECTORIZE_INDEX)

    # region: vectorize_query
    def query(self, vector: list, allowed_groups: list, top_k: int) -> dict:
        import requests

        url = "{base}/accounts/{acct}/vectorize/v2/indexes/{index}/query".format(
            base=C.CF_API_BASE, acct=self.account, index=self.index)
        body = {
            "vector": vector,
            "topK": top_k,
            "returnMetadata": "all",
            # $in is the operator Vectorize supports for "one of these groups".
            "filter": {C.CF_METADATA_FIELD: {"$in": allowed_groups}},
        }
        response = requests.post(
            url, headers={"Authorization": "Bearer " + self.token}, json=body,
            timeout=30)
        response.raise_for_status()
        return response.json()["result"]
    # endregion: vectorize_query
