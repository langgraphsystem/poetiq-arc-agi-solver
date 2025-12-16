"""
Mockup Agent — Create Product Mockups and Previews
Generates realistic product mockups for marketplace listings.

Features:
- Template-based mockups
- AI-generated lifestyle scenes
- Multiple mockup variations
- Automatic sizing and positioning
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Literal

from digital_products_mas.integrations.openai_client import OpenAIClient
from digital_products_mas.integrations.google_client import GoogleClient


class MockupTemplate(Enum):
    """Available mockup templates"""
    # Wall Art
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    OFFICE = "office"
    GALLERY_WALL = "gallery_wall"

    # Products
    FRAME_WHITE = "frame_white"
    FRAME_BLACK = "frame_black"
    FRAME_WOOD = "frame_wood"

    # POD
    MUG_WHITE = "mug_white"
    TSHIRT_WHITE = "tshirt_white"
    TSHIRT_BLACK = "tshirt_black"
    PILLOW = "pillow"
    TOTE_BAG = "tote_bag"

    # Digital
    IPAD_DISPLAY = "ipad_display"
    DESKTOP_DISPLAY = "desktop_display"


@dataclass
class MockupResult:
    """Result from mockup generation"""
    template: MockupTemplate
    image_bytes: bytes
    preview_url: Optional[str] = None
    dimensions: tuple[int, int] = (0, 0)
    metadata: dict = field(default_factory=dict)

    @property
    def size_kb(self) -> float:
        return len(self.image_bytes) / 1024


class MockupAgent:
    """
    Mockup generation agent.

    Creates product mockups using templates and AI-generated scenes.
    """

    def __init__(self):
        self.openai = OpenAIClient()
        self.google = GoogleClient()

    async def create(
        self,
        product_image: bytes,
        template: MockupTemplate,
        **kwargs,
    ) -> MockupResult:
        """Create mockup with template"""
        return await create_mockup(product_image, template, **kwargs)

    async def create_lifestyle(
        self,
        product_image: bytes,
        scene_description: str,
        **kwargs,
    ) -> MockupResult:
        """Create AI-generated lifestyle mockup"""
        return await create_lifestyle_mockup(product_image, scene_description, **kwargs)

    async def create_set(
        self,
        product_image: bytes,
        templates: list[MockupTemplate],
    ) -> list[MockupResult]:
        """Create multiple mockups in parallel"""
        tasks = [
            create_mockup(product_image, template)
            for template in templates
        ]
        return await asyncio.gather(*tasks)


# === MOCKUP FUNCTIONS ===

async def create_mockup(
    product_image: bytes,
    template: MockupTemplate,
    background_color: str = "#FFFFFF",
    shadow: bool = True,
) -> MockupResult:
    """
    Create mockup using template.

    For production, this would use a mockup service API (Placeit, Renderforest, etc.)
    Here we simulate with AI-enhanced compositing.
    """
    # Template descriptions for AI enhancement
    template_prompts = {
        MockupTemplate.LIVING_ROOM: "modern minimalist living room with white walls, the art print hanging above a gray sofa",
        MockupTemplate.BEDROOM: "cozy bedroom with neutral bedding, the art print on the wall above the bed",
        MockupTemplate.OFFICE: "modern home office with clean desk, the art print on the wall behind",
        MockupTemplate.GALLERY_WALL: "gallery wall arrangement with multiple frames, featuring the art print as centerpiece",
        MockupTemplate.FRAME_WHITE: "simple white frame on white background with subtle shadow",
        MockupTemplate.FRAME_BLACK: "elegant black frame on neutral background",
        MockupTemplate.FRAME_WOOD: "natural wood frame on light background",
        MockupTemplate.MUG_WHITE: "white ceramic mug on marble surface, morning coffee scene",
        MockupTemplate.TSHIRT_WHITE: "white t-shirt flat lay on wooden surface",
        MockupTemplate.TSHIRT_BLACK: "black t-shirt flat lay on concrete surface",
        MockupTemplate.PILLOW: "decorative pillow on neutral sofa",
        MockupTemplate.TOTE_BAG: "canvas tote bag lifestyle shot",
        MockupTemplate.IPAD_DISPLAY: "iPad displaying digital product on desk",
        MockupTemplate.DESKTOP_DISPLAY: "desktop computer showing digital product in office",
    }

    scene = template_prompts.get(template, "product mockup")

    # Use image editing to place product in scene
    openai = OpenAIClient()

    prompt = f"Create a professional product mockup: {scene}. Photorealistic, high quality, perfect lighting, suitable for e-commerce listing."

    try:
        # Generate scene and composite
        result = await openai.edit_image(
            image=product_image,
            prompt=prompt,
            size="1024x1024",
        )

        return MockupResult(
            template=template,
            image_bytes=result.image_bytes,
            dimensions=(1024, 1024),
            metadata={
                "template": template.value,
                "scene": scene,
                "shadow": shadow,
            }
        )
    except Exception as e:
        # Fallback: return original with metadata
        return MockupResult(
            template=template,
            image_bytes=product_image,
            metadata={"error": str(e), "fallback": True}
        )


async def create_lifestyle_mockup(
    product_image: bytes,
    scene_description: str,
    style: Literal["modern", "rustic", "minimal", "luxury"] = "modern",
    use_veo: bool = False,  # For video mockups
) -> MockupResult:
    """
    Create AI-generated lifestyle mockup.

    Uses Imagen 4 or GPT-Image-1 for high-quality scene generation.
    """
    style_modifiers = {
        "modern": "modern minimalist interior, clean lines, neutral colors",
        "rustic": "rustic farmhouse style, warm wood tones, cozy atmosphere",
        "minimal": "ultra minimal scandinavian design, white space, simple",
        "luxury": "luxury high-end interior, premium materials, elegant lighting",
    }

    full_prompt = f"""Professional product lifestyle photography:
{scene_description}
Style: {style_modifiers.get(style, 'modern')}
Requirements: Photorealistic, perfect lighting, e-commerce quality, the product as the focal point."""

    google = GoogleClient()

    try:
        result = await google.generate_image_imagen(
            prompt=full_prompt,
            aspect_ratio="1:1",
            model="imagen-4.0-ultra-generate-001",
        )

        return MockupResult(
            template=MockupTemplate.LIVING_ROOM,  # Generic
            image_bytes=result.first,
            dimensions=(1024, 1024),
            metadata={
                "scene": scene_description,
                "style": style,
                "ai_generated": True,
            }
        )
    except Exception as e:
        # Fallback to OpenAI
        openai = OpenAIClient()
        result = await openai.generate_image(
            prompt=full_prompt,
            size="1024x1024",
            quality="hd",
        )

        return MockupResult(
            template=MockupTemplate.LIVING_ROOM,
            image_bytes=result.image_bytes,
            metadata={"scene": scene_description, "style": style, "fallback": "openai"}
        )


# === PRESET MOCKUP SETS ===

def get_wall_art_mockup_set() -> list[MockupTemplate]:
    """Standard mockup set for wall art"""
    return [
        MockupTemplate.LIVING_ROOM,
        MockupTemplate.FRAME_WHITE,
        MockupTemplate.FRAME_BLACK,
        MockupTemplate.BEDROOM,
    ]


def get_pod_mockup_set(product_type: str) -> list[MockupTemplate]:
    """Mockup set for POD products"""
    sets = {
        "mug": [MockupTemplate.MUG_WHITE],
        "shirt": [MockupTemplate.TSHIRT_WHITE, MockupTemplate.TSHIRT_BLACK],
        "pillow": [MockupTemplate.PILLOW, MockupTemplate.LIVING_ROOM],
        "tote": [MockupTemplate.TOTE_BAG],
    }
    return sets.get(product_type.lower(), [MockupTemplate.LIVING_ROOM])


def get_digital_mockup_set() -> list[MockupTemplate]:
    """Mockup set for digital products"""
    return [
        MockupTemplate.IPAD_DISPLAY,
        MockupTemplate.DESKTOP_DISPLAY,
    ]
