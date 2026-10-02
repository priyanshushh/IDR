import re

from langchain_core.runnables import RunnableLambda

# Defense-in-depth under SYSTEM_PROMPT's own "PROMPT INJECTION" instructions — this
# is a deterministic check that doesn't depend on the model choosing to comply with
# those instructions. Logs matches rather than hard-blocking: the false-positive
# rate hasn't been measured yet, and a wrong block is worse than a missed one until
# it has.
_INJECTION_PATTERNS = [
    r"ignore (all|any|the|previous|above) instructions",
    r"disregard (all|any|the|previous|above)",
    r"you are now",
    r"new instructions?:",
    r"system prompt",
    r"reveal (your|the) (instructions|prompt|system prompt)",
    r"act as (if|though)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def scan_for_injection(text: str) -> list[str]:
    return [p.pattern for p in _COMPILED if p.search(text)]


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")


def _redact(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    return text


# A Runnable (not a bare function) so it composes with `|` into an LCEL chain and
# runs through `.batch()` for a whole list of chunks at once — see
# build_docs/08-observability-and-guardrails.md §2.6.
redact_for_logs = RunnableLambda(_redact).with_config({"run_name": "redact_pii"})
