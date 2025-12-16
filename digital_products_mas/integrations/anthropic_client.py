"""
Anthropic API Client — Claude Opus 4.5, Sonnet 4.5, Haiku 4.5
Async client with extended thinking, effort parameter, and structured outputs.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional, Literal, Any

import anthropic

from digital_products_mas.core.rate_limiter import (
    rate_limiter,
    session_tokens,
    TokenUsage,
    get_model_properties,
)


@dataclass
class ThinkingConfig:
    """Configuration for extended thinking"""
    enabled: bool = True
    budget_tokens: int = 10000


@dataclass
class ClaudeResponse:
    """Response from Claude API"""
    content: str
    thinking: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


class AnthropicClient:
    """
    Async Anthropic client with integrated rate limiting and token tracking.

    Features:
    - Extended thinking (Claude Opus/Sonnet 4.5)
    - Effort parameter (Claude Opus 4.5)
    - Structured outputs (JSON schema)
    - 1M context window (beta)
    - Tool use with thinking
    """

    # Model shortcuts
    OPUS = "claude-opus-4-5-20251101"
    SONNET = "claude-sonnet-4-5-20250929"
    HAIKU = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )

    async def generate(
        self,
        prompt: str,
        model: str = "claude-sonnet-4-5-20250929",
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        effort: Optional[Literal["low", "medium", "high"]] = None,
        thinking: Optional[ThinkingConfig] = None,
        track_tokens: bool = True,
    ) -> ClaudeResponse:
        """
        Generate text with Claude.

        Args:
            prompt: User message
            model: Model ID
            system: System prompt
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            effort: Effort level for Opus 4.5 (low/medium/high)
            thinking: Extended thinking configuration
            track_tokens: Whether to track tokens in session

        Returns:
            ClaudeResponse with content, thinking, and usage
        """
        await rate_limiter.wait(model)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            kwargs["system"] = system

        # Temperature (not compatible with thinking)
        if not thinking or not thinking.enabled:
            kwargs["temperature"] = temperature

        # Extended headers for beta features
        extra_headers = {}

        # Effort parameter (Opus 4.5 only)
        if effort and "opus-4-5" in model:
            extra_headers["anthropic-beta"] = "effort-2025-11-01"
            kwargs["effort"] = effort

        # Extended thinking
        if thinking and thinking.enabled:
            # Override beta header for thinking
            extra_headers["anthropic-beta"] = "interleaved-thinking-2025-05-14"
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking.budget_tokens,
            }

        if extra_headers:
            kwargs["extra_headers"] = extra_headers

        response = await self.client.messages.create(**kwargs)

        # Extract content and thinking
        content = ""
        thinking_content = None

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "thinking":
                thinking_content = block.thinking

        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens

        if track_tokens:
            session_tokens.add(TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
            ))

        return ClaudeResponse(
            content=content,
            thinking=thinking_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: dict,
        model: str = "claude-sonnet-4-5-20250929",
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Generate with guaranteed JSON schema compliance.

        Args:
            prompt: User message
            schema: JSON schema for response format
            model: Model ID
            system: System prompt
            max_tokens: Maximum tokens

        Returns:
            Parsed JSON matching the schema
        """
        await rate_limiter.wait(model)

        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            extra_headers={"anthropic-beta": "structured-outputs-2025-11-13"},
            response_format={
                "type": "json_schema",
                "json_schema": schema,
            },
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        return json.loads(content)

    async def generate_long_context(
        self,
        prompt: str,
        context: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 16000,
    ) -> ClaudeResponse:
        """
        Generate with 1M context window (beta).

        Use for processing very long documents.
        """
        await rate_limiter.wait(model)

        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            extra_headers={"anthropic-beta": "context-1m-2025-08-07"},
            messages=[{
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {prompt}"
            }],
        )

        return ClaudeResponse(
            content=response.content[0].text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            model=model,
        )

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        model: str = "claude-sonnet-4-5-20250929",
        system: Optional[str] = None,
        thinking: bool = True,
    ) -> dict:
        """
        Generate with tool use and optional thinking.

        Args:
            prompt: User message
            tools: List of tool definitions
            model: Model ID
            system: System prompt
            thinking: Enable extended thinking with tools

        Returns:
            Dict with content and tool_calls
        """
        await rate_limiter.wait(model)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "tools": tools,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            kwargs["system"] = system

        if thinking:
            kwargs["extra_headers"] = {
                "anthropic-beta": "interleaved-thinking-2025-05-14"
            }
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": 5000,
            }

        response = await self.client.messages.create(**kwargs)

        tool_calls = [
            block for block in response.content
            if block.type == "tool_use"
        ]

        return {
            "content": response.content,
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            }
        }

    # === CONVENIENCE METHODS ===

    async def quick(
        self,
        prompt: str,
        model: str = "claude-haiku-4-5-20251001",
    ) -> str:
        """Quick generation with Haiku (fast & cheap)"""
        response = await self.generate(prompt, model=model, max_tokens=2000)
        return response.content

    async def deep_think(
        self,
        prompt: str,
        effort: Literal["low", "medium", "high"] = "high",
    ) -> ClaudeResponse:
        """Deep reasoning with Opus 4.5 + effort parameter"""
        return await self.generate(
            prompt=prompt,
            model=self.OPUS,
            effort=effort,
            thinking=ThinkingConfig(enabled=True, budget_tokens=32000),
        )

    async def code(
        self,
        prompt: str,
        thinking: bool = True,
    ) -> ClaudeResponse:
        """Code generation with Sonnet 4.5 (SWE-bench leader)"""
        return await self.generate(
            prompt=prompt,
            model=self.SONNET,
            thinking=ThinkingConfig(enabled=thinking, budget_tokens=16000),
            temperature=0.3,
        )
