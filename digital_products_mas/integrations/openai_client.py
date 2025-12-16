"""
OpenAI API Client — GPT-5, Sora, GPT-Image-1
Async client with rate limiting and token tracking.
"""

import base64
import os
from dataclasses import dataclass
from typing import Optional, Literal

from openai import AsyncOpenAI

from digital_products_mas.core.rate_limiter import (
    rate_limiter,
    session_tokens,
    TokenUsage,
    get_model_properties,
)


@dataclass
class ImageResult:
    """Result from image generation"""
    image_bytes: bytes
    revised_prompt: Optional[str] = None


@dataclass
class VideoResult:
    """Result from video generation"""
    video_bytes: bytes
    duration_sec: int = 0


class OpenAIClient:
    """
    Async OpenAI client with integrated rate limiting and token tracking.

    Supports:
    - Text generation (GPT-5, GPT-5-mini, GPT-4.1)
    - Image generation (GPT-Image-1, DALL-E 3)
    - Video generation (Sora)
    - Audio (TTS, STT)
    - Embeddings
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    # === TEXT GENERATION ===

    async def generate(
        self,
        prompt: str,
        model: str = "gpt-5-mini",
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
        track_tokens: bool = True,
    ) -> tuple[str, int, int]:
        """
        Generate text completion.

        Returns:
            (content, prompt_tokens, completion_tokens)
        """
        await rate_limiter.wait(model)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Model-specific properties
        props = get_model_properties(model)
        if "reasoning_effort" in props:
            kwargs["reasoning_effort"] = props["reasoning_effort"]

        if response_format:
            kwargs["response_format"] = response_format

        response = await self.client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        if track_tokens:
            session_tokens.add(TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
            ))

        return content, prompt_tokens, completion_tokens

    async def generate_json(
        self,
        prompt: str,
        model: str = "gpt-5-mini",
        **kwargs
    ) -> tuple[str, int, int]:
        """Generate with JSON response format"""
        return await self.generate(
            prompt=prompt,
            model=model,
            response_format={"type": "json_object"},
            **kwargs
        )

    # === IMAGE GENERATION ===

    async def generate_image(
        self,
        prompt: str,
        model: str = "gpt-image-1",
        size: str = "1024x1536",  # 2:3 for wall art
        quality: str = "hd",
        style: Optional[str] = None,
    ) -> ImageResult:
        """
        Generate image using GPT-Image-1 or DALL-E 3.

        Sizes:
        - 1024x1024 (square)
        - 1024x1536 (2:3 portrait)
        - 1536x1024 (3:2 landscape)
        """
        await rate_limiter.wait(model)

        kwargs = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "response_format": "b64_json",
            "n": 1,
        }

        if style and model == "dall-e-3":
            kwargs["style"] = style  # "vivid" or "natural"

        response = await self.client.images.generate(**kwargs)

        image_bytes = base64.b64decode(response.data[0].b64_json)
        revised_prompt = getattr(response.data[0], 'revised_prompt', None)

        return ImageResult(
            image_bytes=image_bytes,
            revised_prompt=revised_prompt,
        )

    async def edit_image(
        self,
        image: bytes,
        prompt: str,
        mask: Optional[bytes] = None,
        model: str = "gpt-image-1",
        size: str = "1024x1024",
    ) -> ImageResult:
        """Edit/inpaint an existing image"""
        await rate_limiter.wait(model)

        response = await self.client.images.edit(
            model=model,
            image=image,
            prompt=prompt,
            mask=mask,
            size=size,
            response_format="b64_json",
        )

        return ImageResult(
            image_bytes=base64.b64decode(response.data[0].b64_json)
        )

    # === VIDEO GENERATION (Sora) ===

    async def generate_video(
        self,
        prompt: str,
        model: str = "sora-2025-05-02",
        duration: int = 10,
        resolution: str = "1080p",
        aspect_ratio: str = "16:9",
    ) -> VideoResult:
        """
        Generate video using Sora.

        Note: API structure is speculative based on expected patterns.
        """
        await rate_limiter.wait(model)

        # Sora API (expected structure)
        response = await self.client.videos.generate(
            model=model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
        )

        return VideoResult(
            video_bytes=response.video_bytes,
            duration_sec=duration,
        )

    async def image_to_video(
        self,
        image: bytes,
        prompt: str,
        duration: int = 8,
        model: str = "sora-2025-05-02",
    ) -> VideoResult:
        """Generate video from a starting image"""
        await rate_limiter.wait(model)

        response = await self.client.videos.generate(
            model=model,
            image=image,
            prompt=prompt,
            duration=duration,
        )

        return VideoResult(
            video_bytes=response.video_bytes,
            duration_sec=duration,
        )

    # === AUDIO ===

    async def transcribe(
        self,
        audio: bytes,
        model: str = "gpt-4o-transcribe",
        language: Optional[str] = None,
    ) -> str:
        """Speech-to-text transcription"""
        await rate_limiter.wait(model)

        response = await self.client.audio.transcriptions.create(
            model=model,
            file=audio,
            language=language,
        )
        return response.text

    async def text_to_speech(
        self,
        text: str,
        model: str = "tts-1-hd",
        voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "alloy",
        speed: float = 1.0,
    ) -> bytes:
        """Text-to-speech generation"""
        await rate_limiter.wait(model)

        response = await self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
        )
        return response.content

    # === EMBEDDINGS ===

    async def embed(
        self,
        text: str | list[str],
        model: str = "text-embedding-3-large",
        dimensions: Optional[int] = None,
    ) -> list[list[float]]:
        """Generate embeddings for text"""
        await rate_limiter.wait(model)

        kwargs = {"model": model, "input": text}
        if dimensions:
            kwargs["dimensions"] = dimensions

        response = await self.client.embeddings.create(**kwargs)

        return [item.embedding for item in response.data]
