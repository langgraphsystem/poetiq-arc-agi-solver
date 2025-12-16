"""
Listing Manager Agent — Publish and Manage Marketplace Listings
Handles publishing to Etsy and other marketplaces.

Features:
- Multi-platform publishing (Etsy, Amazon, Shopify)
- Inventory sync
- Listing updates
- Performance tracking
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Literal

from digital_products_mas.core.parallel_experts import iterative_refinement


class ListingStatus(Enum):
    """Listing status"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SOLD_OUT = "sold_out"
    EXPIRED = "expired"
    REMOVED = "removed"


class Platform(Enum):
    """Supported platforms"""
    ETSY = "etsy"
    AMAZON = "amazon"
    SHOPIFY = "shopify"
    EBAY = "ebay"


@dataclass
class Listing:
    """Listing data model"""
    # Core
    id: Optional[str] = None
    sku: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    # Pricing
    price: float = 0.0
    compare_at_price: Optional[float] = None
    currency: str = "USD"

    # Media
    images: list[str] = field(default_factory=list)  # URLs
    video_url: Optional[str] = None

    # Inventory
    quantity: int = 999  # Digital = unlimited
    is_digital: bool = True

    # Platform
    platform: Platform = Platform.ETSY
    status: ListingStatus = ListingStatus.DRAFT

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    platform_listing_id: Optional[str] = None


@dataclass
class PublishResult:
    """Result from publishing"""
    success: bool
    listing_id: Optional[str] = None
    platform_url: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ListingManagerAgent:
    """
    Listing management agent.

    Handles publishing, updates, and sync across platforms.
    """

    def __init__(self, etsy_api_key: Optional[str] = None):
        self.etsy_api_key = etsy_api_key

    async def publish(
        self,
        listing: Listing,
        platform: Platform = Platform.ETSY,
    ) -> PublishResult:
        """Publish listing to platform"""
        if platform == Platform.ETSY:
            return await publish_to_etsy(listing, self.etsy_api_key)
        else:
            return PublishResult(
                success=False,
                errors=[f"Platform {platform.value} not yet implemented"]
            )

    async def update(
        self,
        listing_id: str,
        updates: dict,
        platform: Platform = Platform.ETSY,
    ) -> PublishResult:
        """Update existing listing"""
        return await update_listing(listing_id, updates, platform)

    async def sync(
        self,
        listings: list[Listing],
    ) -> dict:
        """Sync inventory across platforms"""
        return await sync_inventory(listings)


# === PUBLISHING FUNCTIONS ===

async def publish_to_etsy(
    listing: Listing,
    api_key: Optional[str] = None,
) -> PublishResult:
    """
    Publish listing to Etsy.

    Uses Etsy API v3 (placeholder implementation).
    """
    errors = []
    warnings = []

    # Validate listing data
    if not listing.title:
        errors.append("Title is required")
    elif len(listing.title) > 140:
        errors.append(f"Title too long ({len(listing.title)} chars, max 140)")

    if len(listing.tags) != 13:
        warnings.append(f"Etsy recommends 13 tags, got {len(listing.tags)}")

    for i, tag in enumerate(listing.tags):
        if len(tag) > 20:
            errors.append(f"Tag {i+1} exceeds 20 chars: '{tag}'")

    if not listing.description:
        errors.append("Description is required")

    if listing.price <= 0:
        errors.append("Price must be greater than 0")

    if not listing.images:
        errors.append("At least one image is required")

    if errors:
        return PublishResult(success=False, errors=errors, warnings=warnings)

    # Simulate API call (in production, use actual Etsy API)
    # from etsy_api import EtsyClient
    # client = EtsyClient(api_key)
    # response = await client.create_listing(...)

    # Simulated success
    platform_listing_id = f"etsy_{listing.sku}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    platform_url = f"https://www.etsy.com/listing/{platform_listing_id}"

    return PublishResult(
        success=True,
        listing_id=platform_listing_id,
        platform_url=platform_url,
        warnings=warnings,
    )


async def update_listing(
    listing_id: str,
    updates: dict,
    platform: Platform = Platform.ETSY,
) -> PublishResult:
    """
    Update existing listing.

    Supports partial updates.
    """
    errors = []
    warnings = []

    # Validate updates
    if "title" in updates and len(updates["title"]) > 140:
        errors.append("Title exceeds 140 characters")

    if "tags" in updates:
        tags = updates["tags"]
        if len(tags) != 13:
            warnings.append(f"Expected 13 tags, got {len(tags)}")
        for tag in tags:
            if len(tag) > 20:
                errors.append(f"Tag exceeds 20 chars: '{tag}'")

    if errors:
        return PublishResult(success=False, errors=errors, warnings=warnings)

    # Simulate API call
    return PublishResult(
        success=True,
        listing_id=listing_id,
        warnings=warnings,
    )


async def sync_inventory(listings: list[Listing]) -> dict:
    """
    Sync inventory across platforms.

    Returns sync status for each listing.
    """
    results = {}

    for listing in listings:
        # Simulate sync
        results[listing.sku] = {
            "status": "synced",
            "platforms": [listing.platform.value],
            "quantity": listing.quantity,
        }

    return {
        "synced": len(results),
        "failed": 0,
        "details": results,
    }


# === RETRY WITH ITERATIVE FIX ===

async def publish_with_retry(
    listing: Listing,
    max_attempts: int = 3,
) -> PublishResult:
    """
    Publish with automatic error fixing.

    Uses iterative refinement to fix validation errors.
    """
    from digital_products_mas.integrations.unified_llm import llm_call

    async def fix_listing(current: Listing, task: dict, feedback: str) -> Listing:
        """Fix listing issues based on feedback"""
        prompt = f"""Fix this Etsy listing based on the errors:

Current:
- Title: {current.title}
- Tags: {current.tags}
- Description: {current.description[:200]}...

Errors: {feedback}

Return fixed values as JSON:
{{
    "title": "fixed title (max 140 chars)",
    "tags": ["13 tags", "each max 20 chars", ...],
    "description": "fixed description"
}}"""

        result = await llm_call(prompt, model="gpt-5-mini", temperature=0.3)

        import json
        try:
            fixes = json.loads(result.content)
            return Listing(
                sku=current.sku,
                title=fixes.get("title", current.title)[:140],
                tags=[t[:20] for t in fixes.get("tags", current.tags)[:13]],
                description=fixes.get("description", current.description),
                price=current.price,
                images=current.images,
            )
        except:
            return current

    # Try publishing
    for attempt in range(max_attempts):
        result = await publish_to_etsy(listing)

        if result.success:
            return result

        if not result.errors:
            break

        # Fix errors and retry
        feedback = "; ".join(result.errors)
        listing = await fix_listing(listing, {}, feedback)

    return result
