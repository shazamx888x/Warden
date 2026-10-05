"""Control W3: the harmful content check on the caller's input.

W2 asks "is this trying to hijack the assistant?". W3 asks a different
question: "is this a request for something harmful, whoever is asking?". It
runs Llama Guard 3 (or its offline stand-in) on the input and stops the
request if the guard returns an unsafe category.
"""

from __future__ import annotations


# region: harm_check
def harm_block(text: str, llama_guard) -> str:
    """Return a reason if the harm check calls the text unsafe, else ''."""
    harm = llama_guard.classify(text)
    if not harm.safe:
        return "harmful request: {}".format(harm.categories)
    return ""
# endregion: harm_check
