"""Control W2: the injection classifier, applied to the caller's input.

W1's string rules catch the phrasings someone has already written down. W2
asks a trained classifier (Prompt Guard 2, or its offline stand-in) whether
the text reads like an attempt to override the assistant's instructions. If
it does, the request stops here and the model never sees it.

The honest limit: a classifier is narrower than an attacker. A polite,
unusual phrasing scores benign and walks straight past, which is why W4, W5
and W8 sit behind this control rather than relying on it.
"""

from __future__ import annotations


# region: injection_check
def injection_block(text: str, guard) -> str:
    """Return a reason if the classifier calls the text an injection, else ''."""
    verdict = guard.score(text)
    if verdict.label == "malicious":
        return "injection score {}".format(verdict.score)
    return ""
# endregion: injection_check
