"""
Rate Limiter and Token Tracker for Multi-Model LLM Calls
Adapted from ARC-AGI Solver (llm.py)

Features:
- Per-model rate limiting
- Retry with exponential backoff
- Token usage tracking
- Timeout management
- Cost estimation
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from collections import defaultdict

from asynciolimiter import Limiter


# === MODEL CONFIGURATION ===

# Rate limits (requests per second) - from ARC-AGI llm.py pattern
MODEL_RATE_LIMITS: dict[str, float] = {
    # OpenAI
    "gpt-5": 1.0,
    "gpt-5-mini": 2.0,
    "gpt-5-nano": 5.0,
    "gpt-5.1": 1.0,
    "gpt-4.1": 2.0,
    "gpt-4.1-mini": 5.0,
    "gpt-4.1-nano": 10.0,
    "gpt-image-1": 0.5,  # Image gen is slower
    "sora-2025-05-02": 0.2,  # Video gen is very slow
    # Anthropic
    "claude-opus-4-5-20251101": 0.5,
    "claude-sonnet-4-5-20250929": 1.0,
    "claude-haiku-4-5-20251001": 2.0,
    # Google
    "gemini-3-pro": 1.0,
    "gemini-2.5-pro": 2.0,
    "gemini-2.5-flash": 5.0,
    "gemini-2.5-flash-lite": 10.0,
    "imagen-4.0-ultra-generate-001": 0.3,
    "veo-3.0-generate": 0.1,
}

# Pricing per 1M tokens (input/output)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI (input, output)
    "gpt-5": (10.0, 30.0),
    "gpt-5-mini": (2.0, 8.0),
    "gpt-5-nano": (0.15, 0.60),
    "gpt-5.1": (12.0, 36.0),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # Anthropic
    "claude-opus-4-5-20251101": (15.0, 75.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
    # Google
    "gemini-3-pro": (3.50, 10.50),
    "gemini-2.5-pro": (1.25, 5.0),
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.5-flash-lite": (0.02, 0.08),
}

# Model-specific properties (from ARC-AGI llm.py)
MODEL_PROPERTIES: dict[str, dict] = {
    "gpt-5": {"reasoning_effort": "high"},
    "gpt-5.1": {"reasoning_effort": "high"},
    "claude-opus-4-5-20251101": {
        "thinking": {"type": "enabled", "budget_tokens": 32_000}
    },
    "claude-sonnet-4-5-20250929": {
        "thinking": {"type": "enabled", "budget_tokens": 16_000}
    },
    "gemini-2.5-pro": {
        "thinking": {"type": "enabled", "budget_tokens": 16_000}
    },
}


# === RATE LIMITER ===

class RateLimiter:
    """
    Per-model rate limiter using asynciolimiter.
    Adapted from ARC-AGI llm.py limiters pattern.
    """

    def __init__(self):
        self._limiters: dict[str, Limiter] = {}

    def get_limiter(self, model: str) -> Limiter:
        """Get or create limiter for a model"""
        if model not in self._limiters:
            rate = MODEL_RATE_LIMITS.get(model, 1.0)
            self._limiters[model] = Limiter(rate)
        return self._limiters[model]

    async def wait(self, model: str) -> None:
        """Wait for rate limit before making request"""
        limiter = self.get_limiter(model)
        await limiter.wait()


# Global instance
rate_limiter = RateLimiter()


# === TOKEN TRACKER ===

@dataclass
class TokenUsage:
    """Token usage for a single request"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        """Estimate cost in USD"""
        if self.model not in MODEL_PRICING:
            return 0.0
        input_price, output_price = MODEL_PRICING[self.model]
        return (
            (self.prompt_tokens / 1_000_000) * input_price +
            (self.completion_tokens / 1_000_000) * output_price
        )


@dataclass
class SessionTokens:
    """Aggregated token usage for a session"""
    usages: list[TokenUsage] = field(default_factory=list)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(u.prompt_tokens for u in self.usages)

    @property
    def total_completion_tokens(self) -> int:
        return sum(u.completion_tokens for u in self.usages)

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.usages)

    def by_model(self) -> dict[str, dict]:
        """Get usage breakdown by model"""
        by_model: dict[str, dict] = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "cost": 0.0, "requests": 0}
        )
        for u in self.usages:
            by_model[u.model]["prompt"] += u.prompt_tokens
            by_model[u.model]["completion"] += u.completion_tokens
            by_model[u.model]["cost"] += u.cost_usd
            by_model[u.model]["requests"] += 1
        return dict(by_model)

    def add(self, usage: TokenUsage) -> None:
        self.usages.append(usage)

    def to_dict(self) -> dict:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "by_model": self.by_model(),
            "request_count": len(self.usages),
        }


# Global session tracker
session_tokens = SessionTokens()


# === RETRY LOGIC ===

RETRIES = 3
RETRY_DELAY_SEC = 5


@dataclass
class LLMResponse:
    """Response from LLM call"""
    content: str
    prompt_tokens: int
    completion_tokens: int
    duration_sec: float
    model: str


async def call_with_retry(
    call_fn,  # Async function to call
    model: str,
    retries: int = RETRIES,
    timeout: float | None = None,
    max_remaining_time: float | None = None,
    track_tokens: bool = True,
) -> LLMResponse:
    """
    Call LLM with rate limiting and retry logic.
    Adapted from ARC-AGI llm.py.

    Args:
        call_fn: Async function that returns (content, prompt_tokens, completion_tokens)
        model: Model identifier for rate limiting
        retries: Number of retry attempts
        timeout: Per-request timeout
        max_remaining_time: Total time budget remaining
        track_tokens: Whether to track tokens in session

    Returns:
        LLMResponse with content and usage info
    """
    attempt = 1

    while attempt <= retries:
        # Rate limit
        await rate_limiter.wait(model)

        # Calculate effective timeout
        effective_timeout = timeout or 60 * 15  # 15 min default
        if max_remaining_time is not None:
            effective_timeout = min(effective_timeout, max_remaining_time)

        start_time = asyncio.get_event_loop().time()

        try:
            content, prompt_tokens, completion_tokens = await asyncio.wait_for(
                call_fn(),
                timeout=effective_timeout
            )

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            # Track tokens
            if track_tokens:
                usage = TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model=model,
                )
                session_tokens.add(usage)

            return LLMResponse(
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_sec=duration,
                model=model,
            )

        except asyncio.TimeoutError:
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            if max_remaining_time is not None:
                max_remaining_time -= duration
                if max_remaining_time <= 0:
                    raise RuntimeError("Exceeded time allotted to the request")

            if attempt == retries:
                # Return empty response on final timeout
                return LLMResponse(
                    content="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    duration_sec=duration,
                    model=model,
                )

            print(f"Timeout on attempt {attempt}, retrying...")
            await asyncio.sleep(RETRY_DELAY_SEC)
            attempt += 1

        except Exception as e:
            error_name = type(e).__name__

            # Retriable errors (from ARC-AGI)
            retriable = [
                "RateLimitError",
                "InternalServerError",
                "ServiceUnavailableError",
                "APIConnectionError",
                "APIError",
            ]

            if any(err in error_name for err in retriable):
                print(f"Retriable error {error_name} on attempt {attempt}: {e}")
                await asyncio.sleep(RETRY_DELAY_SEC)
                attempt += 1
                continue

            if attempt == retries:
                print(f"Max retries reached. Last error: {e}")
                raise

            print(f"Error on attempt {attempt}: {e}")
            await asyncio.sleep(RETRY_DELAY_SEC)
            attempt += 1

    raise RuntimeError("Retries exceeded")


# === COST ESTIMATION ===

def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate cost for a request"""
    if model not in MODEL_PRICING:
        return 0.0
    input_price, output_price = MODEL_PRICING[model]
    return (
        (prompt_tokens / 1_000_000) * input_price +
        (completion_tokens / 1_000_000) * output_price
    )


def estimate_batch_cost(
    model: str,
    num_requests: int,
    avg_prompt_tokens: int = 2000,
    avg_completion_tokens: int = 500,
) -> float:
    """Estimate cost for a batch of requests"""
    return num_requests * estimate_cost(
        model,
        avg_prompt_tokens,
        avg_completion_tokens
    )


# === UTILITY FUNCTIONS ===

def get_model_properties(model: str) -> dict:
    """Get model-specific properties for API calls"""
    return MODEL_PROPERTIES.get(model, {})


def reset_session_tokens() -> SessionTokens:
    """Reset session token tracker and return the old one"""
    global session_tokens
    old = session_tokens
    session_tokens = SessionTokens()
    return old


def get_session_summary() -> dict:
    """Get current session token summary"""
    return session_tokens.to_dict()
