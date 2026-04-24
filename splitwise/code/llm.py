"""Typed LLM wrapper: Anthropic Messages API + Pydantic structured output."""

from __future__ import annotations

import time
from typing import TypeVar

import anthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLM:
    """Call `configure()` from `init_api()` before `generate`."""

    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None
        self._model: str = ""

    def configure(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def generate(
        self,
        *,
        prompt: str,
        schema: type[T],
        max_tokens: int = 256,
        verbose: bool = True,
    ) -> T:
        """Structured generation: response is parsed and validated as `schema`."""
        if self._client is None:
            raise RuntimeError("LLM not configured; call init_api() first.")
        if verbose:
            print(f"  [api] {prompt}", flush=True)
        start = time.time()
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        elapsed = time.time() - start
        out = response.parsed_output
        if out is None:
            raw = ""
            if response.content:
                block = response.content[0]
                if hasattr(block, "text"):
                    raw = block.text or ""
            raise RuntimeError(
                "Structured LLM response missing parsed_output "
                f"(schema={schema.__name__}). Preview: {raw[:200]!r}"
            )
        if verbose:
            print(f"  [api] ({elapsed:.1f}s) → {out}", flush=True)
        return out


llm = LLM()
