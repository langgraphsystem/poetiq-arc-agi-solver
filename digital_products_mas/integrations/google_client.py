"""
Google AI Client — Gemini 3, Imagen 4, Veo 3
Async client for text, image, and video generation.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional, Literal

import google.generativeai as genai

from digital_products_mas.core.rate_limiter import (
    rate_limiter,
    session_tokens,
    TokenUsage,
)


@dataclass
class GeminiResponse:
    """Response from Gemini API"""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


@dataclass
class ImagenResult:
    """Result from Imagen generation"""
    images: list[bytes]

    @property
    def first(self) -> bytes:
        return self.images[0] if self.images else b""


@dataclass
class VeoResult:
    """Result from Veo video generation"""
    video_bytes: bytes
    duration_sec: int = 0
    has_audio: bool = False


class GoogleClient:
    """
    Async Google AI client with integrated rate limiting.

    Supports:
    - Text generation (Gemini 3 Pro, 2.5 Pro/Flash)
    - Image generation (Gemini 3 Pro Image, Imagen 4)
    - Video generation (Veo 3)
    - Embeddings

    Special capability: Gemini 2.5 Flash is BEST at respecting
    character limits (e.g., 20-char tag limit for Etsy).
    """

    def __init__(self, api_key: Optional[str] = None):
        genai.configure(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        self._gcp_project = os.getenv("GCP_PROJECT")

    # === TEXT GENERATION ===

    async def generate(
        self,
        prompt: str,
        model: str = "gemini-3-pro",
        max_tokens: int = 8192,
        temperature: float = 0.7,
        system: Optional[str] = None,
        response_mime_type: Optional[str] = None,
        track_tokens: bool = True,
    ) -> GeminiResponse:
        """
        Generate text with Gemini.

        Args:
            prompt: User message
            model: Model ID (gemini-3-pro, gemini-2.5-pro, gemini-2.5-flash)
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            system: System instruction
            response_mime_type: Force response format (application/json, etc.)
            track_tokens: Whether to track tokens

        Returns:
            GeminiResponse with content and usage
        """
        await rate_limiter.wait(model)

        model_instance = genai.GenerativeModel(
            model,
            system_instruction=system,
        )

        config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        if response_mime_type:
            config["response_mime_type"] = response_mime_type

        response = await model_instance.generate_content_async(
            prompt,
            generation_config=config,
        )

        content = response.text

        # Estimate tokens (Gemini doesn't always provide exact counts)
        prompt_tokens = len(prompt) // 4
        completion_tokens = len(content) // 4

        if hasattr(response, 'usage_metadata'):
            prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', prompt_tokens)
            completion_tokens = getattr(response.usage_metadata, 'candidates_token_count', completion_tokens)

        if track_tokens:
            session_tokens.add(TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
            ))

        return GeminiResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
        )

    async def generate_json(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
        **kwargs
    ) -> dict:
        """Generate with JSON response format"""
        response = await self.generate(
            prompt=prompt,
            model=model,
            response_mime_type="application/json",
            **kwargs
        )
        return json.loads(response.content)

    # === TAGS GENERATION (Gemini Flash is BEST for this) ===

    async def generate_tags(
        self,
        product_description: str,
        count: int = 13,
        max_chars: int = 20,
    ) -> list[str]:
        """
        Generate tags with strict character limit compliance.

        Gemini 2.5 Flash is the BEST model for respecting
        character limits like Etsy's 20-char tag requirement.

        Args:
            product_description: Product info for tag generation
            count: Number of tags to generate (default 13 for Etsy)
            max_chars: Maximum characters per tag (default 20)

        Returns:
            List of tags, each within the character limit
        """
        prompt = f"""Generate exactly {count} tags for this product.

CRITICAL RULES:
- Each tag MUST be {max_chars} characters or less
- Use multi-word tags (2-3 words)
- NO single-word tags
- Include long-tail keywords
- Include occasion keywords (gift for mom, birthday gift, etc.)

Product: {product_description}

Return ONLY a JSON array of {count} strings, nothing else.
Example: ["custom wall art", "gift for her", "home decor"]"""

        result = await self.generate_json(
            prompt=prompt,
            model="gemini-2.5-flash",
            temperature=0.3,
        )

        # Ensure it's a list
        if isinstance(result, dict):
            result = result.get("tags", [])

        # Enforce limits
        tags = [str(t)[:max_chars] for t in result[:count]]

        return tags

    # === IMAGE GENERATION ===

    async def generate_image_gemini(
        self,
        prompt: str,
        model: str = "gemini-3-pro-image",
    ) -> bytes:
        """
        Native image generation with Gemini 3 Pro Image.

        Uses Gemini's built-in image generation capability.
        """
        await rate_limiter.wait(model)

        model_instance = genai.GenerativeModel(model)
        response = await model_instance.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "image/png"}
        )

        # Extract image bytes from response
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data'):
                    return part.inline_data.data

        raise ValueError("No image generated")

    async def generate_image_imagen(
        self,
        prompt: str,
        model: str = "imagen-4.0-ultra-generate-001",
        aspect_ratio: str = "2:3",
        num_images: int = 1,
    ) -> ImagenResult:
        """
        Generate images with Imagen 4.

        Models:
        - imagen-4.0-ultra-generate-001: Highest quality (up to 2K)
        - imagen-4.0-generate-001: Standard (up to 1080p)
        - imagen-4.0-fast-generate-001: Fast (720p)

        Aspect ratios: "1:1", "2:3", "3:2", "4:3", "3:4", "16:9", "9:16"
        """
        await rate_limiter.wait(model)

        # Using Vertex AI for Imagen 4
        from google.cloud import aiplatform

        if self._gcp_project:
            aiplatform.init(project=self._gcp_project)

        imagen = aiplatform.ImageGenerationModel.from_pretrained(model)
        images = await imagen.generate_images_async(
            prompt=prompt,
            number_of_images=num_images,
            aspect_ratio=aspect_ratio,
            output_format="png",
        )

        return ImagenResult(
            images=[img._image_bytes for img in images]
        )

    # === VIDEO GENERATION (Veo 3) ===

    async def generate_video(
        self,
        prompt: str,
        model: str = "veo-3.0-generate",
        duration_seconds: int = 8,
        resolution: str = "1080p",
        include_audio: bool = True,
    ) -> VeoResult:
        """
        Generate video with Veo 3.

        Unique feature: Veo 3 generates native audio (dialogue, sound effects)!

        Models:
        - veo-3.0-generate: Full features + audio
        - veo-3.0-fast-generate: Quick generation
        - veo-3.1-generate: Extended features, character consistency
        """
        await rate_limiter.wait(model)

        from google.cloud import aiplatform

        if self._gcp_project:
            aiplatform.init(project=self._gcp_project)

        veo = aiplatform.VideoGenerationModel.from_pretrained(model)
        video = await veo.generate_video_async(
            prompt=prompt,
            duration_seconds=duration_seconds,
            resolution=resolution,
            include_audio=include_audio,
        )

        return VeoResult(
            video_bytes=video.video_bytes,
            duration_sec=duration_seconds,
            has_audio=include_audio,
        )

    async def image_to_video(
        self,
        image: bytes,
        prompt: str,
        duration_seconds: int = 8,
        model: str = "veo-3.1-generate",
    ) -> VeoResult:
        """
        Generate video from a starting image.

        Veo 3.1 is recommended for better character consistency.
        """
        await rate_limiter.wait(model)

        from google.cloud import aiplatform

        if self._gcp_project:
            aiplatform.init(project=self._gcp_project)

        veo = aiplatform.VideoGenerationModel.from_pretrained(model)
        video = await veo.generate_video_async(
            image=image,
            prompt=prompt,
            duration_seconds=duration_seconds,
            include_audio=True,
        )

        return VeoResult(
            video_bytes=video.video_bytes,
            duration_sec=duration_seconds,
            has_audio=True,
        )

    # === EMBEDDINGS ===

    async def embed(
        self,
        text: str | list[str],
        model: str = "gemini-embedding-001",
        task_type: str = "retrieval_document",
    ) -> list[list[float]]:
        """
        Generate embeddings.

        Task types:
        - retrieval_document: For documents to be retrieved
        - retrieval_query: For search queries
        - semantic_similarity: For comparing texts
        - classification: For classification tasks
        """
        await rate_limiter.wait(model)

        model_instance = genai.GenerativeModel(model)

        if isinstance(text, str):
            text = [text]

        embeddings = []
        for t in text:
            response = await model_instance.embed_content_async(
                content=t,
                task_type=task_type,
            )
            embeddings.append(response["embedding"])

        return embeddings

    # === CONVENIENCE METHODS ===

    async def quick(
        self,
        prompt: str,
    ) -> str:
        """Quick generation with Flash-Lite (fastest & cheapest)"""
        response = await self.generate(
            prompt,
            model="gemini-2.5-flash-lite",
            max_tokens=2000,
        )
        return response.content

    async def research(
        self,
        prompt: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Research task with Gemini 3 Pro.

        Best for web grounding and complex analysis with 1M context.
        """
        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nTask: {prompt}"

        response = await self.generate(
            full_prompt,
            model="gemini-3-pro",
            max_tokens=16000,
            temperature=0.5,
        )
        return response.content
