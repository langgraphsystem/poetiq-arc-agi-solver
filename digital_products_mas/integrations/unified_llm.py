"""
Unified LLM Interface — Route to appropriate provider
Adapted from ARC-AGI llm.py pattern

Single interface for all LLM providers with automatic routing,
rate limiting, retry logic, and token tracking.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, Literal, Any

from digital_products_mas.core.rate_limiter import (
    rate_limiter,
    session_tokens,
    TokenUsage,
    RETRIES,
    RETRY_DELAY_SEC,
)


@dataclass
class LLMResult:
    """Unified result from any LLM provider"""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    duration_sec: float = 0.0
    thinking: Optional[str] = None  # For Claude extended thinking

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# Provider detection based on model name
def _detect_provider(model: str) -> Literal["openai", "anthropic", "google"]:
    """Detect provider from model name"""
    model_lower = model.lower()

    if any(x in model_lower for x in ["gpt", "o3", "o4", "sora", "dall-e", "tts", "whisper"]):
        return "openai"

    if any(x in model_lower for x in ["claude", "opus", "sonnet", "haiku"]):
        return "anthropic"

    if any(x in model_lower for x in ["gemini", "imagen", "veo", "palm"]):
        return "google"

    # Default to OpenAI for unknown models
    return "openai"


class UnifiedLLM:
    """
    Unified interface for all LLM providers.

    Automatically routes to the correct provider based on model name.
    Includes rate limiting, retry logic, and token tracking.

    Usage:
        llm = UnifiedLLM()
        result = await llm.generate("Hello", model="gpt-5-mini")
        result = await llm.generate("Hello", model="claude-sonnet-4-5")
        result = await llm.generate("Hello", model="gemini-2.5-flash")
    """

    def __init__(self):
        self._openai = None
        self._anthropic = None
        self._google = None

    def _get_openai(self):
        if self._openai is None:
            from .openai_client import OpenAIClient
            self._openai = OpenAIClient()
        return self._openai

    def _get_anthropic(self):
        if self._anthropic is None:
            from .anthropic_client import AnthropicClient
            self._anthropic = AnthropicClient()
        return self._anthropic

    def _get_google(self):
        if self._google is None:
            from .google_client import GoogleClient
            self._google = GoogleClient()
        return self._google

    async def generate(
        self,
        prompt: str,
        model: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        retries: int = RETRIES,
        **kwargs
    ) -> LLMResult:
        """
        Generate text using any model.

        Automatically routes to the correct provider and handles
        rate limiting and retries.

        Args:
            prompt: User message
            model: Model ID (auto-detects provider)
            system: System prompt/instruction
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            retries: Number of retry attempts
            **kwargs: Provider-specific options

        Returns:
            LLMResult with content and usage
        """
        provider = _detect_provider(model)
        attempt = 1

        while attempt <= retries:
            start_time = asyncio.get_event_loop().time()

            try:
                if provider == "openai":
                    client = self._get_openai()
                    content, p_tokens, c_tokens = await client.generate(
                        prompt=prompt,
                        model=model,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        track_tokens=False,  # We track here
                    )
                    thinking = None

                elif provider == "anthropic":
                    client = self._get_anthropic()
                    response = await client.generate(
                        prompt=prompt,
                        model=model,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        thinking=kwargs.get("thinking"),
                        effort=kwargs.get("effort"),
                        track_tokens=False,
                    )
                    content = response.content
                    p_tokens = response.prompt_tokens
                    c_tokens = response.completion_tokens
                    thinking = response.thinking

                else:  # google
                    client = self._get_google()
                    response = await client.generate(
                        prompt=prompt,
                        model=model,
                        system=system,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        track_tokens=False,
                    )
                    content = response.content
                    p_tokens = response.prompt_tokens
                    c_tokens = response.completion_tokens
                    thinking = None

                duration = asyncio.get_event_loop().time() - start_time

                # Track tokens centrally
                session_tokens.add(TokenUsage(
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    model=model,
                ))

                return LLMResult(
                    content=content,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    model=model,
                    duration_sec=duration,
                    thinking=thinking,
                )

            except Exception as e:
                error_name = type(e).__name__

                # Retriable errors
                retriable = [
                    "RateLimitError",
                    "InternalServerError",
                    "ServiceUnavailableError",
                    "APIConnectionError",
                    "APIError",
                    "Timeout",
                ]

                if any(err in error_name or err in str(e) for err in retriable):
                    if attempt < retries:
                        print(f"Retriable error on attempt {attempt}: {e}")
                        await asyncio.sleep(RETRY_DELAY_SEC)
                        attempt += 1
                        continue

                raise

        raise RuntimeError(f"Failed after {retries} attempts")


# Global instance for convenience
_unified_llm = UnifiedLLM()


async def llm_call(
    prompt: str,
    model: str,
    **kwargs
) -> LLMResult:
    """
    Convenience function for quick LLM calls.

    Usage:
        result = await llm_call("Hello", "gpt-5-mini")
        result = await llm_call("Think deeply", "claude-opus-4-5", effort="high")
    """
    return await _unified_llm.generate(prompt, model, **kwargs)


# === BATCH PROCESSING ===

async def llm_batch(
    prompts: list[str],
    model: str,
    max_concurrent: int = 5,
    **kwargs
) -> list[LLMResult]:
    """
    Process multiple prompts with concurrency control.

    Args:
        prompts: List of prompts to process
        model: Model to use for all prompts
        max_concurrent: Maximum concurrent requests
        **kwargs: Additional options passed to generate

    Returns:
        List of LLMResult in same order as prompts
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(prompt: str) -> LLMResult:
        async with semaphore:
            return await llm_call(prompt, model, **kwargs)

    tasks = [process_one(p) for p in prompts]
    return await asyncio.gather(*tasks)


# === MODEL SELECTION HELPERS ===

def best_for_task(task: str) -> str:
    """
    Get recommended model for a specific task.

    Tasks:
    - "titles": Creative title generation
    - "tags": Tag generation with char limits
    - "description": Long-form content
    - "code": Code generation
    - "analysis": Deep analysis
    - "fast": Quick responses
    - "cheap": Cost-optimized
    """
    recommendations = {
        "titles": "gpt-5-mini",
        "tags": "gemini-2.5-flash",  # BEST for char limits
        "description": "claude-sonnet-4-5-20250929",
        "code": "claude-sonnet-4-5-20250929",
        "analysis": "claude-opus-4-5-20251101",
        "research": "gemini-3-pro",
        "fast": "gpt-4.1-nano",
        "cheap": "gemini-2.5-flash-lite",
    }
    return recommendations.get(task, "gpt-5-mini")
