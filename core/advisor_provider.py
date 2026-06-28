from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal, TypedDict, Union, cast

from django.conf import settings

JsonValue = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]
OpenRouterRole = Literal["system", "user", "assistant"]

_OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_TIMEOUT_SECONDS = 30


class OpenRouterMessage(TypedDict):
    role: OpenRouterRole
    content: str


class OpenRouterError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenRouterResponse:
    content: str
    model: str
    raw: dict[str, JsonValue]


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _OPENROUTER_CHAT_URL,
        timeout_seconds: int = _OPENROUTER_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key if api_key is not None else str(settings.OPENROUTER_API_KEY)
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def chat_completion(
        self,
        *,
        model: str,
        messages: list[OpenRouterMessage],
        temperature: float = 0.2,
    ) -> OpenRouterResponse:
        if not self.api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured.")

        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
        ).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310
            self.base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise OpenRouterError(f"OpenRouter returned HTTP {exc.code}: {error_body}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

        return _parse_openrouter_response(cast(dict[str, JsonValue], response_payload))

    def stream_chat_completion(
        self,
        *,
        model: str,
        messages: list[OpenRouterMessage],
        on_delta: Callable[[str], None],
        temperature: float = 0.2,
    ) -> OpenRouterResponse:
        if not self.api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured.")

        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310
            self.base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        content_parts: list[str] = []
        response_model = ""
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                for stream_payload in _iter_openrouter_stream_payloads(response):
                    response_model = _stream_model(stream_payload, response_model)
                    delta = _stream_delta(stream_payload)
                    if delta:
                        content_parts.append(delta)
                        on_delta(delta)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise OpenRouterError(f"OpenRouter returned HTTP {exc.code}: {error_body}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

        content = "".join(content_parts)
        return OpenRouterResponse(content=content, model=response_model, raw={})


def _parse_openrouter_response(payload: dict[str, JsonValue]) -> OpenRouterResponse:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError("OpenRouter response did not include choices.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenRouterError("OpenRouter choice was malformed.")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenRouterError("OpenRouter choice did not include a message.")
    content = message.get("content")
    if not isinstance(content, str):
        raise OpenRouterError("OpenRouter message did not include text content.")
    model = payload.get("model")
    return OpenRouterResponse(content=content, model=str(model or ""), raw=payload)


def _iter_openrouter_stream_payloads(lines: Iterable[bytes]) -> Iterable[dict[str, JsonValue]]:
    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise OpenRouterError("OpenRouter stream chunk was malformed.")
        error = payload.get("error")
        if error:
            raise OpenRouterError(f"OpenRouter stream returned an error: {error}")
        yield cast(dict[str, JsonValue], payload)


def _stream_model(payload: dict[str, JsonValue], current_model: str) -> str:
    model = payload.get("model")
    if isinstance(model, str):
        return model
    return current_model


def _stream_delta(payload: dict[str, JsonValue]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenRouterError("OpenRouter stream choice was malformed.")
    delta = first_choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""
