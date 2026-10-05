"""The two classifiers Warden leans on, offline and real.

  Prompt Guard  (control W2)  scores a piece of text for prompt injection intent
  Llama Guard   (control W3)  classifies a request or answer as safe or unsafe

Both have an OFFLINE stand-in and a REAL backend. The stand-ins are honest
about being stand-ins: they are labelled everywhere they are used, and the
guide reports "measured against the offline simulator". The real backends are
Prompt Guard 2 on your own machine or an Oracle VM (Hugging Face transformers)
and Llama Guard 3 on Cloudflare Workers AI (REST). Both are VERIFIED against
documentation on constants.DOCS_CHECKED_DATE and NOT yet run against a real
deployment.

The offline Prompt Guard stand-in is deliberately NARROWER than the attacker
simulator in offline_llm.py. It scores the obvious phrasings the development
attacks use and misses many of the held out carriers, which is the whole
reason W2 is not the only injection control: W4 removes hostile text from
documents before they are ever indexed, and W8 refuses the dangerous action
even when an injection slips past the classifier.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from warden import constants as C
from warden.backends.offline_llm import normalise_for_model


@dataclass
class InjectionVerdict:
    score: float
    label: str            # "malicious" or "benign"
    backend: str


@dataclass
class HarmVerdict:
    safe: bool
    categories: list
    backend: str


# region: offline_prompt_guard
# Signals of injection intent, with weights. This is a STAND IN for Prompt
# Guard 2 and it is deliberately keyed to the obvious phrasings. It scans the
# normalised text (zero width stripped, base64 decoded, tags removed) because a
# real classifier reads the decoded form.
_INJECTION_SIGNALS = [
    (r"ignore (?:all|any|your|the)? ?(?:previous|prior|above)", 0.9),
    (r"disregard (?:your|the|all)", 0.85),
    (r"system prompt|system message", 0.6),
    (r"your (?:exact )?instructions|your configuration|your setup", 0.5),
    (r"(?:reveal|repeat|recite|print).{0,20}(?:secret|token|prompt|instruction)", 0.5),
    (r"unrestricted mode|developer mode|do anything", 0.6),
    (r"you are now|from now on you", 0.4),
]


class OfflinePromptGuard:
    name = "offline"

    def score(self, text: str) -> InjectionVerdict:
        scanned = normalise_for_model(text)
        total = 0.0
        for pattern, weight in _INJECTION_SIGNALS:
            if re.search(pattern, scanned, re.IGNORECASE):
                total += weight
        score = round(min(1.0, total), 4)
        label = "malicious" if score >= C.CLASSIFIER_THRESHOLD else "benign"
        return InjectionVerdict(score=score, label=label, backend=self.name)
# endregion: offline_prompt_guard


# region: offline_llama_guard
# Llama Guard's MLCommons hazard categories, abbreviated. The stand-in flags
# the simulator's harm marker and a few explicit request shapes. It is NOT a
# real safety model and the guide never pretends it is.
HAZARD_CATEGORIES = {
    "S1": "Violent crimes", "S2": "Non-violent crimes", "S9": "Indiscriminate weapons",
    "S10": "Hate", "S11": "Suicide and self-harm",
}
_HARM_SIGNALS = [
    (r"\[\[HARMFUL_CONTENT_WITHHELD", "S2"),
    (r"threatening message|make .* resign|harass|demean", "S10"),
    (r"dangerous weapon|explosive", "S9"),
    (r"without their (?:knowledge|consent)|access .* account", "S2"),
]


class OfflineLlamaGuard:
    name = "offline"

    def classify(self, text: str) -> HarmVerdict:
        found = []
        for pattern, category in _HARM_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(category)
        return HarmVerdict(safe=not found, categories=sorted(set(found)),
                           backend=self.name)
# endregion: offline_llama_guard


# ---------------------------------------------------------------------------
# Real Prompt Guard 2, via Hugging Face transformers. Gated model: accept the
# licence on Hugging Face and log in first. Runs on CPU on the Oracle Always
# Free VM. VERIFIED against the model card, NOT yet run here.
# ---------------------------------------------------------------------------
class TransformersPromptGuard:
    name = "prompt_guard_2"

    def __init__(self) -> None:
        from transformers import pipeline  # lazy

        self.pipe = pipeline(
            "text-classification",
            model=os.environ.get("PROMPT_GUARD_MODEL", C.PROMPT_GUARD_MODEL),
            truncation=True, max_length=C.PROMPT_GUARD_MAX_TOKENS)

    # region: real_prompt_guard
    def score(self, text: str) -> InjectionVerdict:
        result = self.pipe(text)[0]
        # The model labels text "MALICIOUS" or "BENIGN"; take the probability
        # of malicious as the score.
        malicious = result["label"].upper().startswith("MAL")
        score = result["score"] if malicious else 1.0 - result["score"]
        score = round(float(score), 4)
        label = "malicious" if score >= C.CLASSIFIER_THRESHOLD else "benign"
        return InjectionVerdict(score=score, label=label, backend=self.name)
    # endregion: real_prompt_guard


# ---------------------------------------------------------------------------
# Real Llama Guard 3 on Cloudflare Workers AI. VERIFIED against the model page,
# NOT yet run.
# ---------------------------------------------------------------------------
class CloudflareLlamaGuard:
    name = "llama_guard_3"

    def __init__(self) -> None:
        self.account = os.environ["CF_ACCOUNT_ID"]
        self.token = os.environ["CF_API_TOKEN"]

    # region: real_llama_guard
    def classify(self, text: str) -> HarmVerdict:
        import requests

        url = "{base}/accounts/{acct}/ai/run/{model}".format(
            base=C.CF_API_BASE, acct=self.account, model=C.CF_MODEL_GUARD)
        response = requests.post(
            url, headers={"Authorization": "Bearer " + self.token},
            json={"messages": [{"role": "user", "content": text}]}, timeout=30)
        response.raise_for_status()
        verdict = response.json()["result"].get("response") or ""
        # Workers AI may return the verdict as an object instead of text.
        if isinstance(verdict, dict):
            cats = [str(c).upper() for c in verdict.get("categories") or []]
            return HarmVerdict(safe=verdict.get("safe", True) is not False,
                               categories=cats, backend=self.name)
        verdict = str(verdict).strip()
        # Llama Guard returns "safe" or "unsafe\n<comma separated categories>".
        first = verdict.splitlines()[0].strip().lower() if verdict else "safe"
        if first == "safe":
            return HarmVerdict(safe=True, categories=[], backend=self.name)
        cats = []
        for line in verdict.splitlines()[1:]:
            cats += [c.strip().upper() for c in line.split(",") if c.strip()]
        return HarmVerdict(safe=False, categories=cats, backend=self.name)
    # endregion: real_llama_guard


# ---------------------------------------------------------------------------
# Prompt Guard 2 running as a small HTTP service on the Oracle VM
# (infra/oracle/prompt_guard_service.md). Set PROMPT_GUARD_URL to the service's
# /score address and W2 uses it. VERIFIED against the model card, NOT yet run.
# ---------------------------------------------------------------------------
class RemotePromptGuard:
    name = "prompt_guard_2_remote"

    def __init__(self, url: str) -> None:
        self.url = url

    def score(self, text: str) -> InjectionVerdict:
        import requests

        response = requests.post(self.url, json={"text": text}, timeout=10)
        response.raise_for_status()
        score = round(float(response.json()["score"]), 4)
        label = "malicious" if score >= C.CLASSIFIER_THRESHOLD else "benign"
        return InjectionVerdict(score=score, label=label, backend=self.name)


def get_prompt_guard(backend: str | None = None):
    """W2's classifier. The offline stand-in unless you point it somewhere.

    PROMPT_GUARD_URL set: the real Prompt Guard 2 service on your Oracle VM.
    backend "prompt_guard_2": the real model, run on this machine.
    Anything else: the offline stand-in every number in the guide uses.
    """
    url = os.environ.get("PROMPT_GUARD_URL")
    if url and backend != "offline":
        return RemotePromptGuard(url)
    name = (backend or os.environ.get("WARDEN_BACKEND") or "offline").lower()
    return TransformersPromptGuard() if name == "prompt_guard_2" else OfflinePromptGuard()


def get_llama_guard(backend: str | None = None):
    name = (backend or os.environ.get("WARDEN_BACKEND") or "offline").lower()
    return CloudflareLlamaGuard() if name == "cloudflare" else OfflineLlamaGuard()
