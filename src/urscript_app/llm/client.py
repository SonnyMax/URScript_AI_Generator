from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError
from urscript_app.config import get_settings


class LLMUnavailableError(Exception):
    pass


class LLMTimeoutError(Exception):
    pass


class LLMError(Exception):
    pass


def get_client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.lm_studio_base_url, api_key=s.lm_studio_api_key, timeout=s.lm_studio_timeout)


def chat_completion(messages: list[dict], temperature: float | None = None, max_tokens: int | None = None) -> str:
    s = get_settings()
    client = get_client()
    try:
        response = client.chat.completions.create(
            model=s.lm_studio_model,
            messages=messages,
            temperature=temperature if temperature is not None else s.lm_studio_temperature,
            max_tokens=max_tokens if max_tokens is not None else s.lm_studio_max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""
    except APIConnectionError as e:
        raise LLMUnavailableError(f"LM Studio unreachable at {s.lm_studio_base_url}: {e}") from e
    except APITimeoutError as e:
        raise LLMTimeoutError(f"LM Studio request timed out after {s.lm_studio_timeout}s") from e
    except APIStatusError as e:
        raise LLMError(f"LM Studio API error {e.status_code}: {e.message}") from e
