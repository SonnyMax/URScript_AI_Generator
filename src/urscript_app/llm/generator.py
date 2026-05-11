import re
from dataclasses import dataclass

from urscript_app.llm.client import chat_completion
from urscript_app.llm.prompts import build_messages


class EmptyGenerationError(Exception):
    pass


@dataclass
class GenerationResult:
    code: str
    raw_response: str


_FENCE_RE = re.compile(r"```(?:urscript)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_code(raw: str) -> str:
    match = _FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    # Fallback: try the whole response if it looks like URScript
    stripped = raw.strip()
    if stripped.startswith("def ") or stripped.startswith("program"):
        return stripped
    raise EmptyGenerationError("No URScript code block found in LLM response")


def generate_urscript(natural_language: str) -> GenerationResult:
    messages = build_messages(natural_language)
    raw = chat_completion(messages)
    code = _extract_code(raw)
    return GenerationResult(code=code, raw_response=raw)
